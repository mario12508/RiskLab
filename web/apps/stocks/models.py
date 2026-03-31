__all__ = ()

from django.db import models


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
        ("bank", "Банк"),
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
        help_text="Текущая дивидендная доходность",
    )
    dividend_history = models.TextField(
        blank=True,
        verbose_name="Дивидендная история",
        help_text='Например: "Cтабильно платит дивиденды с 2010 года"',
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
        help_text="Текущая стоимость акции",
    )
    open_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Цена открытия (OPEN)",
        help_text="Для сравнения с началом дня",
    )
    high_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Максимум за день (HIGH)",
        help_text="Для оценки волатильности",
    )
    low_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Минимум за день (LOW)",
        help_text="Для оценки волатильности",
    )
    volume = models.BigIntegerField(
        default=0,
        verbose_name="Объем в штуках (VOLUME)",
        help_text="Ликвидность акции",
    )
    value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        verbose_name="Оборот в рублях (VALUE)",
        help_text="Денежный объем торгов",
    )
    change = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Изменение в рублях (CHANGE)",
        help_text="Прибыль/убыток за день",
    )
    change_percent = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        verbose_name="Изменение в процентах (CHANGEPERCENT)",
        help_text="Относительное изменение",
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

    def __str__(self):
        return f"{self.ticker} - {self.name}"


class StockHistory(models.Model):
    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name="price_history",
        verbose_name="Акция",
    )
    date = models.DateField(
        verbose_name="Дата",
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
    close_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Цена закрытия",
    )
    volume = models.BigIntegerField(
        default=0,
        verbose_name="Объем торгов",
    )

    class Meta:
        verbose_name = "История цен"
        verbose_name_plural = "Истории цен"

    def __str__(self):
        return f"{self.stock.ticker} - {self.date}"


class Scenario(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="Название",
    )
    description = models.TextField(
        verbose_name="Описание",
    )

    impacts = models.JSONField(
        verbose_name="Коэффициенты изменения",
    )

    class Meta:
        verbose_name = "Сценарий"
        verbose_name_plural = "Сценарии"

    def __str__(self):
        return self.name
