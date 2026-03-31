__all__ = ()

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
            total += holding.stock.last_price * holding.quantity

        return total

    def update_total_value(self):
        self.total_value = self.calculate_total_value()
        self.save(update_fields=["total_value"])


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
