__all__ = ()

import csv
from io import TextIOWrapper

from apps.stocks.models import Scenario, ScenarioImpact, Stock, StockHistory


from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path


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
        "created_at",
        "last_price",
        "change_percent",
        "volume",
    )
    list_filter = (
        "stock",
        "created_at",
    )
    search_fields = (
        "stock__ticker",
        "stock__name",
    )
    readonly_fields = ("created_at",)


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "description",
    )
    search_fields = ("name",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("import-csv/", self.import_csv, name="import_csv"),
        ]
        return custom_urls + urls

    def import_csv(self, request):
        """
        Импортирует csv файл с данными влияния сценариев на акции
        тикеры к верхнему регистру
        используется update_or_create(обновляет связи)
        """
        if request.method == "POST":
            csv_file = request.FILES.get("csv_file")
            scenario_name = request.POST.get("scenario_name")
            scenario_description = request.POST.get("scenario_description")

            if not csv_file or not scenario_name:
                messages.error(
                    request,
                    "Необходимо указать название сценария и загрузить CSV файл",
                )
                return HttpResponseRedirect(request.path_info)

            scenario, created = Scenario.objects.get_or_create(
                name=scenario_name,
                defaults={
                    "description": scenario_description,
                },
            )

            csv_data = TextIOWrapper(csv_file.file, encoding="utf-8")
            reader = csv.DictReader(csv_data, delimiter=";")

            imported_count = 0
            for row in reader:
                ticker = row.get("ticker", "").strip().upper()
                coefficient = row.get("coefficient", 0)
                explanation = row.get("explanation", "")

                try:
                    stock = Stock.objects.get(ticker=ticker)
                    ScenarioImpact.objects.update_or_create(
                        scenario=scenario,
                        stock=stock,
                        defaults={
                            "coefficient": coefficient,
                            "explanation": explanation,
                        },
                    )
                    imported_count += 1
                except Stock.DoesNotExist:
                    pass

            return HttpResponseRedirect("../")

        return render(request, "admin/import_scenario.html", {})

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_url"] = "import-csv/"
        return super().changelist_view(request, extra_context=extra_context)


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
