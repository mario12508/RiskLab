__all__ = ()

from apps.game.models import Game, GameHolding, GamePlayer, GameTransaction

from django.contrib import admin


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "creator",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "name",
        "creator__username",
    )


@admin.register(GamePlayer)
class GamePlayerAdmin(admin.ModelAdmin):
    list_display = (
        "player_name",
        "game",
        "user",
        "cash",
        "total_value",
    )
    list_filter = ("game",)
    search_fields = (
        "player_name",
        "user__username",
    )


@admin.register(GameHolding)
class GameHoldingAdmin(admin.ModelAdmin):
    list_display = ("player", "stock", "quantity", "average_price")
    search_fields = ("player__player_name", "stock__ticker")


@admin.register(GameTransaction)
class GameTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "player",
        "stock",
        "type",
        "quantity",
        "price",
        "created_at",
    )
    list_filter = ("type",)
    search_fields = ("player__player_name", "stock__ticker")
