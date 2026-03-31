__all__ = ()

from apps.stocks.models import Stock
from apps.stocks.services.moex_api import MOEXService
from apps.trading.models import PersonalHolding, PersonalPortfolio

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect
from django.views.generic import DetailView, ListView


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
            portfolio, created = PersonalPortfolio.objects.get_or_create(
                user=self.request.user,
                defaults={"cash": 1000000, "total_value": 1000000},
            )
            context["portfolio"] = portfolio

            try:
                holding = PersonalHolding.objects.get(
                    portfolio=portfolio,
                    stock=self.object,
                )
                context["user_holding"] = holding
            except PersonalHolding.DoesNotExist:
                context["user_holding"] = None

        return context


@staff_member_required
def refresh_all_prices(request):
    if request.method == "POST":
        MOEXService.update_all_stocks()

    return redirect("stocks:list")
