__all__ = ()

import json
from datetime import timedelta

import numpy as np
import pandas as pd
import requests
from scipy import optimize
from apps.stocks.models import Stock, StockHistory
from apps.trading.models import PersonalPortfolio, PersonalTransaction

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView


class PortfolioView(LoginRequiredMixin, TemplateView):
    template_name = "trading/portfolio.html"
    INDEX_TICKER = "IMOEX"
    RISK_FREE_RATE = 0.08

    def xnpv(self, rate, cashflows):
        if rate <= -1.0:
            return float('inf')

        t0 = cashflows.index[0]
        return sum([
            cf / (1 + rate) ** ((t - t0).days / 365.0)
            for t, cf in cashflows.items()
        ])

    def xirr(self, cashflows):
        if cashflows.empty or not ((cashflows < 0).any() and (cashflows > 0).any()):
            return 0.0

        try:
            return optimize.brentq(lambda r: self.xnpv(r, cashflows), -0.99, 10.0)
        except Exception:
            try:
                return optimize.newton(lambda r: self.xnpv(r, cashflows), 0.1)
            except Exception:
                return 0.0

    def _get_moex_index_series(self, start_date, end_date):
        base_url = (
            "https://iss.moex.com/iss/history/engines/stock/markets/index/"
            f"securities/{self.INDEX_TICKER}.json"
        )
        rows = []
        offset = 0

        while True:
            try:
                response = requests.get(
                    base_url,
                    params={
                        "from": start_date.isoformat(),
                        "till": end_date.isoformat(),
                        "start": offset,
                    },
                    timeout=3,
                )
                response.raise_for_status()
                payload = response.json()
            except Exception:
                break

            history = payload.get("history", {})
            cols = history.get("columns", [])
            data = history.get("data", [])
            if not data:
                break

            rows.extend(data)
            offset += len(data)
            if len(data) < 100 or offset >= 200:
                break

        if not rows:
            return pd.Series(dtype=float)

        df = pd.DataFrame(rows, columns=cols)
        if "TRADEDATE" not in df.columns:
            return pd.Series(dtype=float)

        close_col = "CLOSE" if "CLOSE" in df.columns else "LEGALCLOSEPRICE"
        if close_col not in df.columns:
            return pd.Series(dtype=float)

        df[close_col] = pd.to_numeric(df[close_col], errors="coerce")
        df["TRADEDATE"] = pd.to_datetime(df["TRADEDATE"])
        df = df.dropna(subset=[close_col]).drop_duplicates(subset=["TRADEDATE"])
        if df.empty:
            return pd.Series(dtype=float)

        return pd.Series(df[close_col].values, index=df["TRADEDATE"]).sort_index()

    def _build_stock_price_map(self, holdings, start_date, end_date):
        stock_ids = list(holdings.values_list("stock_id", flat=True))
        if not stock_ids:
            return {}

        hist_qs = StockHistory.objects.filter(
            stock_id__in=stock_ids,
            created_at__date__gte=start_date - timedelta(days=7),
            created_at__date__lte=end_date,
        ).values_list("stock_id", "created_at", "last_price")

        records = {}
        for stock_id, created_at, last_price in hist_qs:
            by_stock = records.setdefault(stock_id, {})
            by_stock[pd.Timestamp(created_at.date())] = float(last_price)
        return records

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        portfolio, _ = PersonalPortfolio.objects.get_or_create(
            user=self.request.user,
            defaults={"cash": 1000000, "total_value": 1000000},
        )
        portfolio.update_total_value()

        holdings = portfolio.holdings.select_related("stock").all()
        transactions = PersonalTransaction.objects.filter(
            portfolio=portfolio
        ).select_related("stock").order_by("-created_at")
        tx_chrono = list(transactions.order_by("created_at"))

        total_invested = sum(h.average_price * h.quantity for h in holdings)
        total_profit = portfolio.total_value - portfolio.cash - total_invested
        profit_percent = (
                    total_profit / total_invested * 100) if total_invested > 0 else 0

        annual_dividend = sum(
            float(h.current_value) * (float(h.stock.dividend_yield) / 100) for
            h in holdings)
        dividend_yield_on_cost = (annual_dividend / float(
            total_invested) * 100) if total_invested > 0 else 0

        irr, twr, volatility, sharpe, max_drawdown = 0.0, 0.0, 0.0, 0.0, 0.0
        irr_is_valid, sharpe_is_valid = True, True
        beta, alpha = 0.0, 0.0
        performance_dates, performance_values, moex_values = [], [], []
        portfolio_returns, moex_returns = [], []
        sector_alloc, holdings_alloc = {}, {}
        analytics_notes = []
        portfolio_growth_pct, moex_growth_pct = 0.0, 0.0

        if tx_chrono:
            start_investment_date = tx_chrono[0].created_at.date()
            actual_days = (timezone.now().date() - start_investment_date).days
            context["analysis_period_days"] = actual_days
            try:
                cf_list = []
                cf_list.append({"date": tx_chrono[0].created_at.date(),
                                "amount": -1_000_000.0})

                for t in tx_chrono:
                    pass

                cf_list.append({
                    "date": timezone.now().date(),
                    "amount": float(portfolio.total_value),
                })

                df_cf = pd.DataFrame(cf_list).groupby('date').sum()['amount']

                if not (df_cf < 0).any() or not (df_cf > 0).any():
                    irr = 0.0
                else:
                    irr = self.xirr(df_cf) * 100

                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=120)

                date_range = pd.date_range(start=start_date, end=end_date)
                stock_map = {h.stock_id: h.stock for h in holdings}
                history_map = self._build_stock_price_map(holdings, start_date, end_date)
                price_series_map = {}

                for h in holdings:
                    stock = h.stock
                    stock_series = pd.Series(dtype=float)
                    if stock.id in history_map:
                        stock_series = pd.Series(history_map[stock.id]).sort_index()

                    if stock_series.empty:
                        stock_series = pd.Series(index=date_range, data=float(stock.last_price))
                    else:
                        stock_series = stock_series.reindex(date_range, method="ffill").bfill().fillna(float(stock.last_price))

                    price_series_map[stock.id] = stock_series

                s_portfolio = pd.Series(index=date_range, data=float(portfolio.cash))
                for h in holdings:
                    series = price_series_map.get(h.stock_id)
                    if series is None:
                        series = pd.Series(index=date_range, data=float(h.stock.last_price))
                    s_portfolio = s_portfolio.add(series * float(h.quantity), fill_value=0.0)
                s_portfolio = s_portfolio.astype(float)

                s_moex = self._get_moex_index_series(start_date, end_date)
                if s_moex.empty:
                    analytics_notes.append(
                        "История IMOEX недоступна (проверьте доступ к ISS MOEX)."
                    )
                    s_moex = pd.Series(index=date_range, data=np.nan)
                else:
                    s_moex = s_moex.reindex(date_range, method="ffill").bfill()

                if not s_moex.empty and s_moex.notna().any() and s_moex.iloc[0] > 0:
                    s_moex_scaled = s_moex / s_moex.iloc[0] * s_portfolio.iloc[0]
                else:
                    s_moex_scaled = pd.Series(index=date_range, data=np.nan)

                performance_dates = s_portfolio.index.strftime("%d.%m.%Y").tolist()
                performance_values = [round(float(v), 2) for v in s_portfolio.tolist()]
                moex_values = [
                    round(float(v), 2) if pd.notna(v) else None
                    for v in s_moex_scaled.tolist()
                ]

                daily_returns = s_portfolio.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
                moex_daily_returns = s_moex.pct_change().dropna()

                if len(daily_returns) > 0:
                    cumulative_returns = (1 + daily_returns).cumprod()
                    twr = (cumulative_returns.iloc[-1] - 1) * 100

                    rolling_max = cumulative_returns.cummax()
                    drawdown = (cumulative_returns - rolling_max) / rolling_max
                    max_drawdown = drawdown.min() * 100

                    if len(daily_returns) >= 20:
                        std_dev = daily_returns.std()
                        if pd.isna(std_dev) or std_dev == 0:
                            volatility = 0.0
                            sharpe = 0.0
                            sharpe_is_valid = False
                        else:
                            volatility = std_dev * np.sqrt(252) * 100
                            sharpe = (daily_returns.mean() * 252 - self.RISK_FREE_RATE) / (volatility / 100)
                            if not np.isfinite(sharpe) or abs(sharpe) > 10:
                                sharpe = 0.0
                                sharpe_is_valid = False
                    else:
                        sharpe_is_valid = False
                else:
                    analytics_notes.append(
                        "Недостаточно дневной истории для расчета риск-метрик."
                    )

                aligned = pd.concat([daily_returns, moex_daily_returns], axis=1).dropna()
                if len(aligned) > 2:
                    aligned.columns = ["portfolio", "moex"]
                    moex_var = aligned["moex"].var()
                    if moex_var and not pd.isna(moex_var):
                        beta = float(aligned["portfolio"].cov(aligned["moex"]) / moex_var)
                    alpha = float(
                        (aligned["portfolio"].mean() - beta * aligned["moex"].mean()) * 252 * 100
                    )

                portfolio_returns = [round(float(v) * 100, 3) for v in daily_returns.tolist()]
                moex_returns = [
                    round(float(v) * 100, 3) if pd.notna(v) else None
                    for v in moex_daily_returns.reindex(daily_returns.index).tolist()
                ]

                if len(performance_values) > 1 and performance_values[0]:
                    portfolio_growth_pct = ((performance_values[-1] / performance_values[0]) - 1) * 100
                valid_moex = [v for v in moex_values if v is not None]
                if len(valid_moex) > 1 and valid_moex[0]:
                    moex_growth_pct = ((valid_moex[-1] / valid_moex[0]) - 1) * 100

            except Exception as e:
                print(f"Error in analytics calculation: {e}")
                analytics_notes.append(
                    "Ошибка расчета аналитики. Проверьте корректность цен/сделок в базе."
                )

        for h in holdings:
            sector = h.stock.get_sector_display()
            sector_alloc[sector] = sector_alloc.get(sector, 0) + float(
                h.current_value)
            holdings_alloc[h.stock.ticker] = float(h.current_value)

        if not performance_values:
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            base = float(portfolio.total_value)
            performance_dates = [yesterday.strftime("%d.%m.%Y"), today.strftime("%d.%m.%Y")]
            performance_values = [base, base]
            moex_values = [base, base]
            portfolio_returns = [0.0]
            moex_returns = [0.0]
            analytics_notes.append(
                "Недостаточно исторических цен в базе. Сформирован базовый график из 2 точек."
            )

        print(f"DEBUG: Dates count: {len(performance_dates)}")
        print(f"DEBUG: Values head: {performance_values[:5]}")
        print(f"DEBUG: Portfolio total: {portfolio.total_value}")
        chart_payload = json.dumps({
            "performanceDates": performance_dates,
            "performanceValues": performance_values,
            "moexValues": moex_values,
            "portfolioReturns": portfolio_returns,
            "moexReturns": moex_returns,
            "sectorAlloc": sector_alloc,
            "holdingsAlloc": holdings_alloc,
            "portfolioGrowthPct": round(portfolio_growth_pct, 3),
            "moexGrowthPct": round(moex_growth_pct, 3),
        }, ensure_ascii=False)

        context.update({
            "portfolio": portfolio,
            "holdings": holdings,
            "total_invested": total_invested,
            "total_profit": total_profit,
            "profit_percent": profit_percent,
            "annual_dividend": annual_dividend,
            "dividend_yield_on_cost": dividend_yield_on_cost,
            "irr": irr,
            "twr": twr,
            "volatility": volatility,
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "beta": beta,
            "alpha": alpha,
            "sector_alloc": sector_alloc,
            "holdings_alloc": holdings_alloc,
            "chart_payload": {
                "performanceDates": performance_dates,
                "performanceValues": [v if v is not None else 0 for v in
                                      performance_values],
                "moexValues": [v if v is not None else 0 for v in moex_values],
                "portfolioGrowthPct": round(portfolio_growth_pct, 3),
                "moexGrowthPct": round(moex_growth_pct, 3),
                "sectorAlloc": sector_alloc,
                "holdingsAlloc": holdings_alloc,
                "portfolioReturns": portfolio_returns,
                "moexReturns": moex_returns,
            },
            "portfolio_growth_pct": portfolio_growth_pct,
            "moex_growth_pct": moex_growth_pct,
            "analytics_notes": analytics_notes,
            "irr_is_valid": irr_is_valid,
            "sharpe_is_valid": sharpe_is_valid,
            "transactions": transactions,
        })
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
