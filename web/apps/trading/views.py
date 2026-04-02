__all__ = ()

from datetime import timedelta

from apps.stocks.models import Stock, StockHistory
from apps.trading.models import PersonalPortfolio, PersonalTransaction
from apps.trading.services.moex_api import MOEXService

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

import numpy as np

import pandas as pd
from prophet import Prophet
from scipy import optimize


class PortfolioView(LoginRequiredMixin, TemplateView):
    template_name = "trading/portfolio.html"
    RISK_FREE_RATE = 0.08

    def xnpv(self, rate, cashflows):
        if rate <= -1.0:
            return float("inf")

        t0 = cashflows.index[0]
        return sum(
            [
                cf / (1 + rate) ** ((t - t0).days / 365.0)
                for t, cf in cashflows.items()
            ],
        )

    def xirr(self, cashflows):
        if cashflows.empty or not (
            (cashflows < 0).any() and (cashflows > 0).any()
        ):
            return 0.0

        try:
            return optimize.brentq(
                lambda r: self.xnpv(r, cashflows),
                -0.99,
                10.0,
            )
        except Exception:
            try:
                return optimize.newton(lambda r: self.xnpv(r, cashflows), 0.1)
            except Exception:
                return 0.0

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

    def _calculate_historical_portfolio_series(self, holdings, portfolio_cash,
                                               start_date, end_date):

        date_range = pd.date_range(start=start_date, end=end_date)
        history_map = self._build_stock_price_map(holdings, start_date,
                                                  end_date)

        price_series_map = {}
        for h in holdings:
            stock = h.stock
            stock_series = pd.Series(dtype=float)
            if stock.id in history_map:
                stock_series = pd.Series(history_map[stock.id]).sort_index()
            if stock_series.empty:
                stock_series = pd.Series(index=date_range,
                                         data=float(stock.last_price))
            else:
                stock_series = stock_series.reindex(date_range,
                                                    method="ffill").bfill().fillna(
                    float(stock.last_price))
            price_series_map[stock.id] = stock_series

        s_portfolio = pd.Series(index=date_range, data=float(portfolio_cash))
        for h in holdings:
            series = price_series_map.get(h.stock_id)
            if series is None:
                series = pd.Series(index=date_range,
                                   data=float(h.stock.last_price))
            s_portfolio = s_portfolio.add(series * float(h.quantity),
                                          fill_value=0.0)
        return s_portfolio.astype(float)

    def _prophet_forecast(self, historical_series, horizon_years,
                          horizon_label):
        df = pd.DataFrame({
            'ds': historical_series.index,
            'y': historical_series.values
        })
        df = df.dropna()

        if len(df) < 30:
            return None

        days = int(horizon_years * 365.25)
        if days < 1:
            days = 1

        try:
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                interval_width=0.95,
                uncertainty_samples=1000
            )
            model.fit(df)

            future = model.make_future_dataframe(periods=days,
                                                 include_history=False)
            forecast = model.predict(future)

            predicted = forecast['yhat'].iloc[-1]
            return float(predicted) if predicted > 0 else None
        except Exception:
            return None

    def _gbm_forecast(self, S0, mu, sigma, horizon_years, dt=1 / 252,
                      n_simulations=10000):
        if sigma == 0 or mu == 0 or S0 <= 0:
            return None, None, None

        n_steps = int(horizon_years / dt)
        if n_steps < 1:
            n_steps = 1
        dt_adj = horizon_years / n_steps

        prices = np.zeros((n_simulations, n_steps + 1))
        prices[:, 0] = S0

        for step in range(1, n_steps + 1):
            z = np.random.normal(0, 1, n_simulations)
            prices[:, step] = prices[:, step - 1] * np.exp(
                (mu - 0.5 * sigma ** 2) * dt_adj + sigma * np.sqrt(dt_adj) * z
            )

        final_prices = prices[:, -1]
        pessimistic = np.percentile(final_prices, 5)
        expected = np.median(final_prices)
        optimistic = np.percentile(final_prices, 95)

        return pessimistic, expected, optimistic

    def _calculate_dynamic_weights(self, mu, sigma, horizon_years):
        base_gbm_weight = max(0.3, min(0.7, 1.0 - horizon_years / 20.0))
        base_prophet_weight = 1.0 - base_gbm_weight

        volatility_factor = min(0.3, sigma * 0.5)
        gbm_weight = base_gbm_weight + volatility_factor
        prophet_weight = 1.0 - gbm_weight

        gbm_weight = max(0.2, min(0.8, gbm_weight))
        prophet_weight = 1.0 - gbm_weight

        return gbm_weight, prophet_weight

    def _ensemble_forecast(self, S0, mu, sigma, historical_series):
        horizons = [
            {'name': '1m', 'years': 1 / 12, 'label': '1 месяц'},
            {'name': '1y', 'years': 1.0, 'label': '1 год'},
            {'name': '10y', 'years': 10.0, 'label': '10 лет'}
        ]

        forecast_result = {}

        for h in horizons:
            horizon_years = h['years']
            horizon_label = h['label']

            gbm_pess, gbm_exp, gbm_opt = self._gbm_forecast(S0, mu, sigma,
                                                            horizon_years)
            prophet_exp = self._prophet_forecast(historical_series,
                                                 horizon_years, horizon_label)
            gbm_weight, prophet_weight = self._calculate_dynamic_weights(mu,
                                                                         sigma,
                                                                         horizon_years)

            if prophet_exp is not None and gbm_exp is not None:
                expected = (gbm_weight * gbm_exp) + (
                            prophet_weight * prophet_exp)
                spread_gbm = (gbm_opt - gbm_pess) * gbm_weight
                prophet_spread = 2 * sigma * S0 * np.sqrt(
                    horizon_years) * prophet_weight
                total_spread = spread_gbm + prophet_spread
                pessimistic = expected - total_spread * 0.7
                optimistic = expected + total_spread * 0.7
                pessimistic = max(pessimistic, 0.01)
            elif gbm_exp is not None:
                expected = gbm_exp
                pessimistic = gbm_pess
                optimistic = gbm_opt
            elif prophet_exp is not None:
                expected = prophet_exp
                spread = 2 * sigma * S0 * np.sqrt(
                    horizon_years) if sigma > 0 else expected * 0.2
                pessimistic = max(expected - spread, 0.01)
                optimistic = expected + spread
            else:
                expected = S0 * (1 + mu) ** horizon_years
                pessimistic = expected * 0.7
                optimistic = expected * 1.3

            forecast_result[horizon_years] = {
                'pessimistic': pessimistic,
                'expected': expected,
                'optimistic': optimistic,
                'weights': {'gbm': round(gbm_weight, 2),
                            'prophet': round(prophet_weight, 2)}
            }

        return forecast_result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        portfolio, _ = PersonalPortfolio.objects.get_or_create(
            user=self.request.user,
            defaults={"cash": 1000000, "total_value": 1000000},
        )
        portfolio.update_total_value()

        holdings = portfolio.holdings.select_related("stock").all()
        transactions = (
            PersonalTransaction.objects.filter(portfolio=portfolio)
            .select_related("stock")
            .order_by("-created_at")
        )
        tx_chrono = list(transactions.order_by("created_at"))

        total_invested = sum(h.average_price * h.quantity for h in holdings)
        total_profit = portfolio.total_value - portfolio.cash - total_invested
        profit_percent = (
                    total_profit / total_invested * 100) if total_invested > 0 else 0

        annual_dividend = sum(
            float(h.current_value) * (float(h.stock.dividend_yield) / 100) for
            h in holdings
        )
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
        daily_returns = pd.Series(dtype=float)
        actual_days = 0

        mu = None
        sigma = None
        forecast_chart_data = None
        fc_1m = fc_1y = fc_10y = None
        weights_data = {}

        if tx_chrono:
            start_investment_date = tx_chrono[0].created_at.date()
            actual_days = (timezone.now().date() - start_investment_date).days
            context["analysis_period_days"] = actual_days

            try:
                cf_list = [{"date": tx_chrono[0].created_at.date(),
                            "amount": -1_000_000.0}]
                for t in tx_chrono:
                    if t.type == 'DEPOSIT':
                        cf_list.append({"date": t.created_at.date(),
                                        "amount": -float(t.amount)})
                    elif t.type == 'WITHDRAW':
                        cf_list.append({"date": t.created_at.date(),
                                        "amount": float(t.amount)})
                cf_list.append({"date": timezone.now().date(),
                                "amount": float(portfolio.total_value)})
                df_cf = pd.DataFrame(cf_list).groupby("date").sum()["amount"]
                if (df_cf < 0).any() and (df_cf > 0).any():
                    irr = self.xirr(df_cf) * 100
                else:
                    irr = 0.0

                end_date = timezone.now().date()
                start_date_hist = end_date - timedelta(days=730)
                historical_portfolio_series = self._calculate_historical_portfolio_series(
                    holdings, portfolio.cash, start_date_hist, end_date
                )

                if historical_portfolio_series is not None and len(
                        historical_portfolio_series) > 20:
                    daily_returns_hist = historical_portfolio_series.pct_change().dropna()
                    if len(daily_returns_hist) > 20:
                        mu_daily = daily_returns_hist.mean()
                        sigma_daily = daily_returns_hist.std()
                        mu = (1 + mu_daily) ** 252 - 1
                        sigma = sigma_daily * np.sqrt(252)
                        mu = max(-0.10, min(mu, 0.40))
                        sigma = max(0.01, min(sigma, 0.60))
                    else:
                        analytics_notes.append(
                            "Недостаточно исторических данных (меньше 20 точек) для расчёта ожидаемой доходности и волатильности.")
                else:
                    analytics_notes.append(
                        "Нет исторического ряда портфеля для расчёта mu/sigma.")

                start_date = end_date - timedelta(days=120)
                date_range = pd.date_range(start=start_date, end=end_date)
                history_map = self._build_stock_price_map(holdings, start_date,
                                                          end_date)

                price_series_map = {}
                for h in holdings:
                    stock = h.stock
                    stock_series = pd.Series(dtype=float)
                    if stock.id in history_map:
                        stock_series = pd.Series(
                            history_map[stock.id]).sort_index()
                    if stock_series.empty:
                        stock_series = pd.Series(index=date_range,
                                                 data=float(stock.last_price))
                    else:
                        stock_series = stock_series.reindex(date_range,
                                                            method="ffill").bfill().fillna(
                            float(stock.last_price))
                    price_series_map[stock.id] = stock_series

                s_portfolio = pd.Series(index=date_range,
                                        data=float(portfolio.cash))
                for h in holdings:
                    series = price_series_map.get(h.stock_id)
                    if series is None:
                        series = pd.Series(index=date_range,
                                           data=float(h.stock.last_price))
                    s_portfolio = s_portfolio.add(series * float(h.quantity),
                                                  fill_value=0.0)
                s_portfolio = s_portfolio.astype(float)

                s_moex = MOEXService.get_moex_index_series(start_date,
                                                           end_date)
                if s_moex.empty:
                    analytics_notes.append("История IMOEX недоступна.")
                    s_moex = pd.Series(index=date_range, data=np.nan)
                else:
                    s_moex = s_moex.reindex(date_range, method="ffill").bfill()

                if (not s_moex.empty and s_moex.notna().any() and s_moex.iloc[
                    0] > 0):
                    s_moex_scaled = s_moex / s_moex.iloc[0] * s_portfolio.iloc[
                        0]
                else:
                    s_moex_scaled = pd.Series(index=date_range, data=np.nan)

                performance_dates = s_portfolio.index.strftime(
                    "%d.%m.%Y").tolist()
                performance_values = [round(float(v), 2) for v in
                                      s_portfolio.tolist()]
                moex_values = [round(float(v), 2) if pd.notna(v) else None for
                               v in s_moex_scaled.tolist()]

                daily_returns = s_portfolio.pct_change().replace(
                    [np.inf, -np.inf], np.nan).dropna()
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
                            sharpe = (
                                                 daily_returns.mean() * 252 - self.RISK_FREE_RATE) / (
                                                 volatility / 100)
                            if not np.isfinite(sharpe) or abs(sharpe) > 10:
                                sharpe = 0.0
                                sharpe_is_valid = False
                    else:
                        sharpe_is_valid = False
                else:
                    analytics_notes.append(
                        "Недостаточно дневной истории для риск-метрик.")

                aligned = pd.concat([daily_returns, moex_daily_returns],
                                    axis=1).dropna()
                if len(aligned) > 2:
                    aligned.columns = ["portfolio", "moex"]
                    moex_var = aligned["moex"].var()
                    if moex_var and not pd.isna(moex_var):
                        beta = aligned["portfolio"].cov(
                            aligned["moex"]) / moex_var
                        beta = float(beta)
                    alpha = aligned["portfolio"].mean() - beta * aligned[
                        "moex"].mean()
                    alpha = float(alpha * 25200)

                portfolio_returns = [round(float(v) * 100, 3) for v in
                                     daily_returns.tolist()]
                moex_returns = [
                    round(float(v) * 100, 3) if pd.notna(v) else None
                    for v in
                    moex_daily_returns.reindex(daily_returns.index).tolist()
                ]
                if len(performance_values) > 1 and performance_values[0]:
                    portfolio_growth_pct = (performance_values[-1] /
                                            performance_values[0] - 1) * 100
                valid_moex = [v for v in moex_values if v is not None]
                if len(valid_moex) > 1 and valid_moex[0]:
                    moex_growth_pct = (valid_moex[-1] / valid_moex[
                        0] - 1) * 100

                if mu is not None and sigma is not None and historical_portfolio_series is not None:
                    ensemble_forecast = self._ensemble_forecast(
                        S0=float(portfolio.total_value),
                        mu=mu,
                        sigma=sigma,
                        historical_series=historical_portfolio_series
                    )

                    forecast_chart_data = {
                        'horizons': ['Сейчас', '1 месяц', '1 год', '10 лет'],
                        'pessimistic': [
                            float(portfolio.total_value),
                            ensemble_forecast.get(1 / 12, {}).get(
                                'pessimistic', float(portfolio.total_value)),
                            ensemble_forecast.get(1.0, {}).get('pessimistic',
                                                               float(
                                                                   portfolio.total_value)),
                            ensemble_forecast.get(10.0, {}).get('pessimistic',
                                                                float(
                                                                    portfolio.total_value))
                        ],
                        'expected': [
                            float(portfolio.total_value),
                            ensemble_forecast.get(1 / 12, {}).get('expected',
                                                                  float(
                                                                      portfolio.total_value)),
                            ensemble_forecast.get(1.0, {}).get('expected',
                                                               float(
                                                                   portfolio.total_value)),
                            ensemble_forecast.get(10.0, {}).get('expected',
                                                                float(
                                                                    portfolio.total_value))
                        ],
                        'optimistic': [
                            float(portfolio.total_value),
                            ensemble_forecast.get(1 / 12, {}).get('optimistic',
                                                                  float(
                                                                      portfolio.total_value)),
                            ensemble_forecast.get(1.0, {}).get('optimistic',
                                                               float(
                                                                   portfolio.total_value)),
                            ensemble_forecast.get(10.0, {}).get('optimistic',
                                                                float(
                                                                    portfolio.total_value))
                        ],
                        'weights': {
                            '1m': ensemble_forecast.get(1 / 12, {}).get(
                                'weights', {'gbm': 0.5, 'prophet': 0.5}),
                            '1y': ensemble_forecast.get(1.0, {}).get('weights',
                                                                     {
                                                                         'gbm': 0.5,
                                                                         'prophet': 0.5}),
                            '10y': ensemble_forecast.get(10.0, {}).get(
                                'weights', {'gbm': 0.5, 'prophet': 0.5}),
                        }
                    }

                    fc_1m = ensemble_forecast.get(1 / 12, {})
                    fc_1y = ensemble_forecast.get(1.0, {})
                    fc_10y = ensemble_forecast.get(10.0, {})
                    weights_data = {
                        '1m': fc_1m.get('weights',
                                        {'gbm': 0.5, 'prophet': 0.5}),
                        '1y': fc_1y.get('weights',
                                        {'gbm': 0.5, 'prophet': 0.5}),
                        '10y': fc_10y.get('weights',
                                          {'gbm': 0.5, 'prophet': 0.5}),
                    }
                else:
                    analytics_notes.append(
                        "Недостаточно данных для построения прогноза (нет mu/sigma или исторического ряда).")

            except Exception as e:
                analytics_notes.append(f"Ошибка расчёта аналитики: {str(e)}")
        else:
            analytics_notes.append("Нет данных о сделках. Прогноз недоступен.")
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            base = float(portfolio.total_value)
            performance_dates = [yesterday.strftime("%d.%m.%Y"),
                                 today.strftime("%d.%m.%Y")]
            performance_values = [base, base]
            moex_values = [base, base]
            portfolio_returns = [0.0]
            moex_returns = [0.0]

        for h in holdings:
            sector = h.stock.get_sector_display()
            sector_alloc[sector] = sector_alloc.get(sector, 0) + float(
                h.current_value)
            holdings_alloc[h.stock.ticker] = float(h.current_value)

        chart_payload = {
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
        }
        if forecast_chart_data:
            chart_payload["forecastChartData"] = forecast_chart_data

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
            "volatility": sigma * 100 if sigma else 0.0,
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "beta": beta,
            "alpha": alpha,
            "sector_alloc": sector_alloc,
            "holdings_alloc": holdings_alloc,

            "forecast_available": fc_1m is not None,
            "forecast_1m": fc_1m.get('expected') if fc_1m else None,
            "forecast_1y": fc_1y.get('expected') if fc_1y else None,
            "forecast_10y": fc_10y.get('expected') if fc_10y else None,
            "forecast_annual_pct": mu * 100 if mu else None,
            "forecast_pessimistic_1m": fc_1m.get(
                'pessimistic') if fc_1m else None,
            "forecast_pessimistic_1y": fc_1y.get(
                'pessimistic') if fc_1y else None,
            "forecast_pessimistic_10y": fc_10y.get(
                'pessimistic') if fc_10y else None,
            "forecast_optimistic_1m": fc_1m.get(
                'optimistic') if fc_1m else None,
            "forecast_optimistic_1y": fc_1y.get(
                'optimistic') if fc_1y else None,
            "forecast_optimistic_10y": fc_10y.get(
                'optimistic') if fc_10y else None,
            "forecast_weights": weights_data,
            "chart_payload": chart_payload,
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
