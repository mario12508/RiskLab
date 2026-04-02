__all__ = ()

from django.db import models
from django.utils import timezone


class Stock(models.Model):
    ticker = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Тикер",
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Название компании",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Описание компании",
    )

    SECTOR_CHOICES = [
        ("oil_gas", "Нефтегаз"),
        ("retail", "Сеть магазинов"),
        ("bank", "IT и финансы"),
        ("metallurgy", "Металлургия"),
        ("transport", "Транспорт"),
        ("it", "IT сектор"),
    ]
    sector = models.CharField(
        max_length=50,
        choices=SECTOR_CHOICES,
        verbose_name="Сектор экономики",
    )

    dividend_yield = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Дивидендная доходность (%)",
    )
    dividend_history = models.TextField(
        blank=True,
        verbose_name="Дивидендная история",
    )

    VOLATILITY_CHOICES = [
        ("low", "Низкая"),
        ("medium", "Средняя"),
        ("high", "Высокая"),
    ]
    volatility = models.CharField(
        max_length=10,
        choices=VOLATILITY_CHOICES,
        verbose_name="Волатильность",
    )

    last_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Последняя цена (LAST)",
    )
    open_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Цена открытия (OPEN)",
    )
    high_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Максимум за день (HIGH)",
    )
    low_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Минимум за день (LOW)",
    )
    volume = models.BigIntegerField(
        default=0,
        verbose_name="Объем в штуках (VOLUME)",
    )
    value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        verbose_name="Оборот в рублях (VALUE)",
    )
    change = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Изменение в рублях (CHANGE)",
    )
    change_percent = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        verbose_name="Изменение в процентах (CHANGEPERCENT)",
    )

    last_price_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Последнее обновление цены",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"
        ordering = ("ticker",)

    def __str__(self):
        return f"{self.ticker} - {self.name}"


class StockHistory(models.Model):
    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name="price_history",
        verbose_name="Акция",
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Дата и время",
    )
    last_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Последняя цена",
    )
    open_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Цена открытия",
    )
    high_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Максимум",
    )
    low_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Минимум",
    )
    volume = models.BigIntegerField(
        default=0,
        verbose_name="Объем торгов",
    )
    value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        verbose_name="Оборот",
    )
    change = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Изменение",
    )
    change_percent = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        verbose_name="Изменение %",
    )

    class Meta:
        verbose_name = "История цен"
        verbose_name_plural = "Истории цен"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.stock.ticker} - {self.created_at}"


class Scenario(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="Название",
    )
    description = models.TextField(
        verbose_name="Описание",
    )

    class Meta:
        verbose_name = "Сценарий"
        verbose_name_plural = "Сценарии"

    def __str__(self):
        return self.name


class ScenarioImpact(models.Model):
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,
        related_name="impacts",
        verbose_name="Сценарий",
    )
    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name="scenario_impacts",
        verbose_name="Акция",
    )
    coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        verbose_name="Коэффициент изменения",
    )
    explanation = models.TextField(
        blank=True,
        verbose_name="Пояснение",
    )

    class Meta:
        verbose_name = "Влияние сценария"
        verbose_name_plural = "Влияния сценариев"

    def __str__(self):
        return (
            f"{self.scenario.name} - {self.stock.ticker}: {self.coefficient}"
        )
