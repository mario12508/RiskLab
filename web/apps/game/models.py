__all__ = ()

import uuid

from django.conf import settings
from django.db import models


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
        return f"/games/play/{self.game_id}/"

    @property
    def players_count(self):
        return self.players.count()


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
            f"{self.player.player_name}: "
            f"{self.stock.ticker} x{self.quantity}"
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
                * 100
            )

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

    class Meta:
        verbose_name = "Сделка в игре"
        verbose_name_plural = "Сделки в игре"

    def __str__(self):
        return (
            f"{self.player.player_name} - {self.get_type_display()} "
            f"{self.quantity} {self.stock.ticker}"
        )
