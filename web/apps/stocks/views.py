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
            portfolio, _ = PersonalPortfolio.objects.get_or_create(
                user=self.request.user,
            )
            context["portfolio"] = portfolio
            context["user_holding"] = PersonalHolding.objects.filter(
                portfolio=portfolio,
                stock=self.object,
            ).first()

        return context


@staff_member_required
def refresh_all_prices(request):
    if request.method == "POST":
        MOEXService.update_all_stocks()

    return redirect("stocks:list")
