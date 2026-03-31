__all__ = ()

from apps.stocks.models import Stock
from apps.trading.models import PersonalPortfolio, PersonalTransaction

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, TemplateView


class PortfolioView(LoginRequiredMixin, TemplateView):
    template_name = "trading/portfolio.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        portfolio, created = PersonalPortfolio.objects.get_or_create(
            user=self.request.user,
            defaults={"cash": 1000000, "total_value": 1000000},
        )

        portfolio.update_total_value()
        holdings = portfolio.holdings.select_related("stock").all()

        total_invested = sum(h.average_price * h.quantity for h in holdings)
        total_profit = portfolio.total_value - portfolio.cash - total_invested

        context.update(
            {
                "portfolio": portfolio,
                "holdings": holdings,
                "total_invested": total_invested,
                "total_profit": total_profit,
                "profit_percent": (
                    (total_profit / total_invested * 100)
                    if total_invested > 0
                    else 0
                ),
            },
        )

        return context


class BuyStockView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        ticker = request.POST.get("ticker")
        quantity = int(request.POST.get("quantity", 0))

        if quantity <= 0:
            return redirect("stocks:detail", ticker=ticker)

        stock = get_object_or_404(Stock, ticker=ticker)
        portfolio, _ = PersonalPortfolio.objects.get_or_create(
            user=request.user,
            defaults={"cash": 1000000, "total_value": 1000000},
        )

        try:
            with transaction.atomic():
                portfolio.buy_stock(stock, quantity)
        except ValueError:
            pass

        return redirect("stocks:detail", ticker=ticker)


class SellStockView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        ticker = request.POST.get("ticker")
        quantity = int(request.POST.get("quantity", 0))

        if quantity <= 0:
            messages.error(request, "Неверное количество")
            return redirect("stocks:detail", ticker=ticker)

        stock = get_object_or_404(Stock, ticker=ticker)

        try:
            portfolio = PersonalPortfolio.objects.get(user=request.user)
        except PersonalPortfolio.DoesNotExist:
            return redirect("stocks:detail", ticker=ticker)

        try:
            with transaction.atomic():
                portfolio.sell_stock(stock, quantity)
        except ValueError:
            pass

        return redirect("stocks:detail", ticker=ticker)


class TransactionHistoryView(LoginRequiredMixin, ListView):
    template_name = "trading/transactions.html"
    context_object_name = "transactions"
    paginate_by = 50

    def get_queryset(self):
        try:
            portfolio = PersonalPortfolio.objects.get(user=self.request.user)
            return portfolio.transactions.select_related("stock").all()
        except PersonalPortfolio.DoesNotExist:
            return PersonalTransaction.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
