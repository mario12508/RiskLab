__all__ = ()

from apps.trading.models import (
    PersonalHolding,
    PersonalPortfolio,
    PersonalTransaction,
)

from django.contrib import admin


@admin.register(PersonalPortfolio)
class PersonalPortfolioAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "cash",
        "total_value",
        "updated_at",
    )
    search_fields = ("user__username",)
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(PersonalHolding)
class PersonalHoldingAdmin(admin.ModelAdmin):
    list_display = (
        "portfolio",
        "stock",
        "quantity",
        "average_price",
    )
    search_fields = (
        "portfolio__user__username",
        "stock__ticker",
    )


@admin.register(PersonalTransaction)
class PersonalTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "portfolio",
        "stock",
        "type",
        "quantity",
        "price",
        "total",
        "created_at",
    )
    list_filter = (
        "type",
        "created_at",
    )
    search_fields = (
        "portfolio__user__username",
        "stock__ticker",
    )
