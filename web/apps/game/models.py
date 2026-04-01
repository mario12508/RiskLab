__all__ = ()

import uuid
import qrcode
from io import BytesIO

from django.core.files import File
from django.conf import settings
from django.db import models
from django.urls import reverse


class Game(models.Model):
    game_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID игры",
    )

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_games",
        verbose_name="Создатель",
    )

    name = models.CharField(
        max_length=200,
        verbose_name="Название игры",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Описание",
    )

    STATUS_CHOICES = [
        ("waiting", "Ожидание игроков"),
        ("active", "Активна"),
        ("finished", "Завершена"),
    ]
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="waiting",
        verbose_name="Статус",
    )

    start_capital = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=1000000,
        verbose_name="Стартовый капитал",
    )

    qr_code = models.ImageField(
        upload_to="game_qr_codes/",
        blank=True,
        null=True,
        verbose_name="QR-код",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Игра"
        verbose_name_plural = "Игры"

    def __str__(self):
        return f"{self.name} ({self.creator.username})"

    @property
    def invite_link(self):
        return f"/game/play/{self.game_id}/"

    @property
    def players_count(self):
        return self.players.count()

    def start_game(self):
        self.status = "active"
        self.save()

    def finish_game(self):
        self.status = "finished"
        self.save()

        for player in self.players.all():
            player.finish_game()

    def generate_qr_code(self):
        link = f"{settings.SITE_URL}{reverse('game:join', args=[self.game_id])}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(link)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")

        self.qr_code.save(f"qr_{self.game_id}.png", File(buffer), save=False)

        return self.qr_code.url


class GamePlayer(models.Model):
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="players",
        verbose_name="Игра",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="game_participations",
        verbose_name="Пользователь",
    )
    player_name = models.CharField(
        max_length=100,
        verbose_name="Имя игрока",
    )
    is_guest = models.BooleanField(
        default=True,
        verbose_name="Гость",
    )

    cash = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Наличные",
    )
    total_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Текущая стоимость",
    )
    final_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Итоговая стоимость",
    )
    rank = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Место",
    )

    sharpe_ratio = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name="Коэффициент Шарпа",
    )
    profit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Прибыль",
    )

    class Meta:
        verbose_name = "Участник игры"
        verbose_name_plural = "Участники игр"

    def __str__(self):
        if self.user:
            return f"{self.user.username} в {self.game.name}"

        return f"{self.player_name} (гость) в {self.game.name}"

    def save(self, *args, **kwargs):
        if self.user:
            self.is_guest = False

        if not self.player_name and self.user:
            self.player_name = self.user.username

        if not self.cash and self.pk is None:
            self.cash = self.game.start_capital
            self.total_value = self.game.start_capital

        super().save(*args, **kwargs)

    def calculate_total_value(self, stress_coefficients=None):
        total = self.cash
        for holding in self.holdings.select_related("stock").all():
            if (
                    stress_coefficients
                    and holding.stock.ticker in stress_coefficients
            ):
                price = (
                        holding.stock.last_price
                        * stress_coefficients[holding.stock.ticker]
                )
            else:
                price = holding.stock.last_price

            total += price * holding.quantity

        return total

    def update_total_value(self):
        self.total_value = self.calculate_total_value()
        self.save(update_fields=["total_value"])

    def finish_game(self):
        self.final_value = self.total_value
        self.profit = self.total_value - self.game.start_capital
        self.save(update_fields=["final_value", "profit"])

    def can_buy(self, stock, quantity):
        return self.cash >= (stock.last_price * quantity)

    def buy_stock(self, stock, quantity):
        cost = stock.last_price * quantity

        if not self.can_buy(stock, quantity):
            raise ValueError(
                f"Недостаточно средств. Доступно: {self.cash:.2f} ₽",
            )

        holding, created = GameHolding.objects.get_or_create(
            player=self,
            stock=stock,
            defaults={"average_price": stock.last_price, "quantity": 0},
        )

        if not created and holding.quantity > 0:
            total_cost = (holding.average_price * holding.quantity) + cost
            new_quantity = holding.quantity + quantity
            holding.average_price = total_cost / new_quantity

        holding.quantity += quantity
        holding.save()

        self.cash -= cost
        self.save()

        GameTransaction.objects.create(
            player=self,
            stock=stock,
            type="buy",
            quantity=quantity,
            price=stock.last_price,
            total=cost,
        )

        self.update_total_value()
        return holding

    def can_sell(self, stock, quantity):
        try:
            holding = GameHolding.objects.get(player=self, stock=stock)
            return holding.quantity >= quantity
        except GameHolding.DoesNotExist:
            return False

    def sell_stock(self, stock, quantity):
        try:
            holding = GameHolding.objects.get(player=self, stock=stock)
        except GameHolding.DoesNotExist:
            raise ValueError("У вас нет таких акций")

        if holding.quantity < quantity:
            raise ValueError(
                f"Недостаточно акций. У вас: {holding.quantity} шт.",
            )

        revenue = stock.last_price * quantity

        holding.quantity -= quantity
        if holding.quantity == 0:
            holding.delete()
        else:
            holding.save()

        self.cash += revenue
        self.save()

        GameTransaction.objects.create(
            player=self,
            stock=stock,
            type="sell",
            quantity=quantity,
            price=stock.last_price,
            total=revenue,
        )

        self.update_total_value()
        return True


class GameHolding(models.Model):
    player = models.ForeignKey(
        GamePlayer,
        on_delete=models.CASCADE,
        related_name="holdings",
        verbose_name="Игрок",
    )
    stock = models.ForeignKey(
        "stocks.Stock",
        on_delete=models.CASCADE,
        verbose_name="Акция",
    )
    quantity = models.IntegerField(
        default=0,
        verbose_name="Количество",
    )
    average_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Средняя цена покупки",
    )

    class Meta:
        verbose_name = "Позиция в игре"
        verbose_name_plural = "Позиции в игре"

    def __str__(self):
        return (
            f"{self.player.player_name}: {self.stock.ticker} x{self.quantity}"
        )

    @property
    def current_value(self):
        return self.stock.last_price * self.quantity

    @property
    def profit_loss(self):
        return (self.stock.last_price - self.average_price) * self.quantity

    @property
    def profit_loss_percent(self):
        if self.average_price > 0:
            return (
                    (self.stock.last_price - self.average_price)
                    / self.average_price
            ) * 100

        return 0


class GameTransaction(models.Model):
    TYPE_CHOICES = [
        ("buy", "Покупка"),
        ("sell", "Продажа"),
    ]

    player = models.ForeignKey(
        GamePlayer,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="Игрок",
    )
    stock = models.ForeignKey(
        "stocks.Stock",
        on_delete=models.CASCADE,
        verbose_name="Акция",
    )
    type = models.CharField(
        max_length=4,
        choices=TYPE_CHOICES,
        verbose_name="Тип операции",
    )
    quantity = models.IntegerField(
        verbose_name="Количество",
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Цена сделки",
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Сумма",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Сделка в игре"
        verbose_name_plural = "Сделки в игре"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.player.player_name} - {self.get_type_display()} "
            f"{self.quantity} {self.stock.ticker}"
        )
