from django.core.management.base import BaseCommand
from apps.stocks.models import Stock
from apps.stocks.services.moex_api import MOEXService


class Command(BaseCommand):
    help = 'Загружает историю цен за 120 дней для всех акций'

    def handle(self, *args, **options):
        stocks = Stock.objects.all()
        self.stdout.write(f"Найдено акций: {stocks.count()}")

        for stock in stocks:
            self.stdout.write(f"Загрузка {stock.ticker}...", ending="")
            count = MOEXService.fetch_and_save_history(stock.ticker, days=120)
            self.stdout.write(self.style.SUCCESS(f" OK (+{count})"))
