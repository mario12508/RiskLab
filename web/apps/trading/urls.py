from apps.trading import views

from django.urls import path

app_name = "trading"
urlpatterns = [
    path("", views.PortfolioView.as_view(), name="portfolio"),
    path("buy/", views.BuyStockView.as_view(), name="buy"),
    path("sell/", views.SellStockView.as_view(), name="sell"),
    path(
        "transactions/",
        views.TransactionHistoryView.as_view(),
        name="transactions",
    ),
]
