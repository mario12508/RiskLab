from apps.game import views

from django.urls import path

app_name = "game"
urlpatterns = [
    path(
        "",
        views.GameListView.as_view(),
        name="list",
    ),
    path(
        "create/",
        views.GameCreateView.as_view(),
        name="create",
    ),
    path(
        "join/<uuid:game_id>/",
        views.GameJoinView.as_view(),
        name="join",
    ),
    path(
        "detail/<uuid:game_id>/",
        views.GameDetailView.as_view(),
        name="detail",
    ),
    path(
        "play/<uuid:game_id>/",
        views.GamePlayView.as_view(),
        name="play",
    ),
    path(
        "start/<uuid:game_id>/",
        views.GameStartView.as_view(),
        name="start",
    ),
    path(
        "results/<uuid:game_id>/",
        views.GameResultsView.as_view(),
        name="results",
    ),
    path(
        "stress/<uuid:game_id>/",
        views.ApplyStressTestView.as_view(),
        name="stress_test",
    ),
    path(
        "buy/<uuid:game_id>/",
        views.GameBuyView.as_view(),
        name="buy",
    ),
    path(
        "sell/<uuid:game_id>/",
        views.GameSellView.as_view(),
        name="sell",
    ),
    path(
        "play/<uuid:game_id>/portfolio/",
        views.GamePortfolioView.as_view(),
        name="portfolio_api",
    ),
    path(
        "qr/<uuid:game_id>/",
        views.GameQRCodeView.as_view(),
        name="qr_code",
    ),
]
