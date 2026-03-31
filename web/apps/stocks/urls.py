from apps.stocks import views

from django.urls import path

app_name = "stocks"
urlpatterns = [
    path("", views.StockListView.as_view(), name="list"),
    path("<str:ticker>/", views.StockDetailView.as_view(), name="detail"),
    path("refresh/all/", views.refresh_all_prices, name="refresh_all"),
]
