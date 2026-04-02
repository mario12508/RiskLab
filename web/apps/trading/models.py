__all__ = ()

from decimal import Decimal

from apps.stocks.models import Stock

from django.conf import settings
from django.db import models


class PersonalPortfolio(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_portfolio",
        verbose_name="Пользователь",
    )
    cash = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=1000000,
        verbose_name="Наличные",
    )
    total_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=1000000,
        verbose_name="Общая стоимость",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Личный портфель"
        verbose_name_plural = "Личные портфели"

    def __str__(self):
        return f"Портфель {self.user.username}"

    def calculate_total_value(self):
        total = self.cash
        for holding in self.holdings.select_related("stock").all():
            total += holding.stock.last_price * Decimal(holding.quantity)

        return total

    def update_total_value(self):
        self.total_value = self.calculate_total_value()
        self.save(update_fields=["total_value"])

    def buy_stock(self, stock, quantity):
        cost = stock.last_price * quantity

        if self.cash < cost:
            raise ValueError(
                f"Недостаточно средств. Доступно: {self.cash:.2f} ₽",
            )

        holding, created = PersonalHolding.objects.get_or_create(
            portfolio=self,
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

        PersonalTransaction.objects.create(
            portfolio=self,
            stock=stock,
            type="buy",
            quantity=quantity,
            price=stock.last_price,
            total=cost,
        )

        self.update_total_value()
        return holding

    def sell_stock(self, stock, quantity):
        try:
            holding = PersonalHolding.objects.get(portfolio=self, stock=stock)
        except PersonalHolding.DoesNotExist:
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

        PersonalTransaction.objects.create(
            portfolio=self,
            stock=stock,
            type="sell",
            quantity=quantity,
            price=stock.last_price,
            total=revenue,
        )

        self.update_total_value()
        return True


class PersonalHolding(models.Model):
    portfolio = models.ForeignKey(
        PersonalPortfolio,
        on_delete=models.CASCADE,
        related_name="holdings",
        verbose_name="Портфель",
    )
    stock = models.ForeignKey(
        Stock,
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
        verbose_name = "Позиция"
        verbose_name_plural = "Позиции"

    def __str__(self):
        return f"{self.stock.ticker}: {self.quantity} шт."

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


class PersonalTransaction(models.Model):
    TYPE_CHOICES = [
        ("buy", "Покупка"),
        ("sell", "Продажа"),
    ]

    portfolio = models.ForeignKey(
        PersonalPortfolio,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="Портфель",
    )
    stock = models.ForeignKey(
        Stock,
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
        verbose_name = "Сделка"
        verbose_name_plural = "Сделки"

    def __str__(self):
        return (
            f"{self.portfolio.user.username} - {self.get_type_display()} "
            f"{self.quantity} {self.stock.ticker}"
        )
