from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView

from apps.stocks.models import Stock
from apps.stocks.services.moex_api import MOEXService
from apps.trading.models import PersonalHolding, PersonalPortfolio


class StockListView(ListView):
    model = Stock
    template_name = "stocks/list.html"
    context_object_name = "stocks"
    paginate_by = 12


class StockDetailView(DetailView):
    model = Stock
    template_name = "stocks/detail.html"
    context_object_name = "stock"
    slug_field = "ticker"
    slug_url_kwarg = "ticker"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            # Получаем или создаем портфель
            portfolio, _ = PersonalPortfolio.objects.get_or_create(
                user=self.request.user
            )
            context["portfolio"] = portfolio
            # Получаем позицию по конкретной акции
            context["user_holding"] = PersonalHolding.objects.filter(
                portfolio=portfolio, stock=self.object
            ).first()
        return context


@login_required
def buy_stock(request):
    if request.method == "POST":
        ticker = request.POST.get("ticker")
        stock = get_object_or_404(Stock, ticker=ticker)
        portfolio = get_object_or_404(PersonalPortfolio, user=request.user)

        try:
            quantity = int(request.POST.get("quantity", 0))
            if quantity <= 0:
                raise ValueError("Количество должно быть больше нуля.")

            # Используем мощный метод из твоей модели!
            with transaction.atomic():
                portfolio.buy_stock(stock, quantity)

            messages.success(request, f"Куплено {quantity} шт. {stock.ticker}")
        except ValueError as e:
            messages.error(request, str(e))

    return redirect("stocks:detail", ticker=ticker)


@login_required
def sell_stock(request):
    if request.method == "POST":
        ticker = request.POST.get("ticker")
        stock = get_object_or_404(Stock, ticker=ticker)
        portfolio = get_object_or_404(PersonalPortfolio, user=request.user)

        try:
            quantity = int(request.POST.get("quantity", 0))
            if quantity <= 0:
                raise ValueError("Количество должно быть больше нуля.")

            # Вызываем метод продажи из модели
            with transaction.atomic():
                portfolio.sell_stock(stock, quantity)

            messages.success(request, f"Продано {quantity} шт. {stock.ticker}")
        except ValueError as e:
            messages.error(request, str(e))

    return redirect("stocks:detail", ticker=ticker)


@staff_member_required
def refresh_all_prices(request):
    if request.method == "POST":
        MOEXService.update_all_stocks()
    return redirect("stocks:list")
