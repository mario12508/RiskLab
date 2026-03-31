__all__ = ()

from apps.stocks.models import Scenario, ScenarioImpact, Stock, StockHistory

from django.contrib import admin


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = (
        "ticker",
        "name",
        "sector",
        "last_price",
        "change_percent",
        "last_price_updated",
    )
    list_filter = (
        "sector",
        "volatility",
    )
    search_fields = (
        "ticker",
        "name",
    )
    readonly_fields = (
        "last_price_updated",
        "created_at",
    )


@admin.register(StockHistory)
class StockHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "stock",
        "date",
        "close_price",
        "volume",
    )
    list_filter = (
        "stock",
        "date",
    )
    search_fields = (
        "stock__ticker",
        "stock__name",
    )


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "description",
    )
    search_fields = ("name",)


@admin.register(ScenarioImpact)
class ScenarioImpactAdmin(admin.ModelAdmin):
    list_display = (
        "scenario",
        "stock",
        "coefficient",
        "explanation",
    )
    list_filter = (
        "scenario",
        "stock",
    )
    search_fields = (
        "scenario__name",
        "stock__ticker",
    )
