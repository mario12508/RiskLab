__all__ = ()

import uuid
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db import transaction
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView, CreateView
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator

from apps.stocks.models import Stock, Scenario
from apps.game.models import Game, GamePlayer, GameHolding, GameTransaction


class GameListView(LoginRequiredMixin, ListView):
    template_name = "game/list.html"
    context_object_name = "games"

    def get_queryset(self):
        return Game.objects.filter(creator=self.request.user).order_by(
            "-created_at"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["created_games"] = self.get_queryset()
        context["participated_games"] = (
            Game.objects.filter(
                players__user=self.request.user,
                status__in=["waiting", "active"],
            )
            .exclude(creator=self.request.user)
            .distinct()
        )
        return context


class GameCreateView(LoginRequiredMixin, TemplateView):
    template_name = "game/create.html"

    def post(self, request, *args, **kwargs):
        name = request.POST.get("name")
        description = request.POST.get("description", "")
        start_capital = request.POST.get("start_capital", 1000000)

        game = Game.objects.create(
            creator=request.user,
            name=name,
            description=description,
            start_capital=start_capital,
        )

        return redirect("game:detail", game_id=game.game_id)


class GameJoinView(TemplateView):
    template_name = "game/join.html"

    def dispatch(self, request, *args, **kwargs):
        self.game = get_object_or_404(Game, game_id=kwargs["game_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["game"] = self.game
        return context

    def post(self, request, *args, **kwargs):
        player_name = request.POST.get("player_name")

        if not player_name:
            messages.error(request, "Введите имя")
            return self.render_to_response(self.get_context_data())

        if GamePlayer.objects.filter(
            game=self.game, player_name=player_name
        ).exists():
            messages.error(request, "Игрок с таким именем уже есть")
            return self.render_to_response(self.get_context_data())

        GamePlayer.objects.create(
            game=self.game,
            player_name=player_name,
            cash=self.game.start_capital,
            total_value=self.game.start_capital,
            user=request.user if request.user.is_authenticated else None,
        )

        if not request.user.is_authenticated:
            request.session["game_player_name"] = player_name
            request.session["game_id"] = str(self.game.game_id)

        return redirect("game:play", game_id=self.game.game_id)


class GameDetailView(LoginRequiredMixin, DetailView):
    model = Game
    template_name = "game/detail.html"
    context_object_name = "game"
    slug_field = "game_id"
    slug_url_kwarg = "game_id"

    def get_queryset(self):
        return Game.objects.filter(creator=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["players"] = self.object.players.all()
        context["scenarios"] = Scenario.objects.all()
        return context


class GamePlayView(TemplateView):
    template_name = "game/play.html"

    def dispatch(self, request, *args, **kwargs):
        self.game = get_object_or_404(Game, game_id=kwargs["game_id"])
        self.player = self._get_player(request)

        if not self.player:
            return redirect("game:game_join", game_id=self.game.game_id)

        if self.game.status == "finished":
            return redirect("game:game_results", game_id=self.game.game_id)

        return super().dispatch(request, *args, **kwargs)

    def _get_player(self, request):
        if request.user.is_authenticated:
            try:
                return GamePlayer.objects.get(
                    game=self.game, user=request.user
                )
            except GamePlayer.DoesNotExist:
                return None
        else:
            player_name = request.session.get("game_player_name")
            session_game_id = request.session.get("game_id")
            if player_name and session_game_id == str(self.game.game_id):
                try:
                    return GamePlayer.objects.get(
                        game=self.game, player_name=player_name
                    )
                except GamePlayer.DoesNotExist:
                    return None

        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        self.player.update_total_value()

        context["game"] = self.game
        context["player"] = self.player
        context["stocks"] = Stock.objects.all()
        context["holdings"] = self.player.holdings.select_related(
            "stock"
        ).all()
        context["scenarios"] = (
            Scenario.objects.all()
            if self.request.user == self.game.creator
            else []
        )
        context["is_creator"] = self.request.user == self.game.creator

        return context


class GameStartView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        game = get_object_or_404(
            Game, game_id=kwargs["game_id"], creator=request.user
        )

        if game.status != "waiting":
            messages.error(request, "Игра уже начата")
            return redirect("game:detail", game_id=game.game_id)

        if game.players.count() == 0:
            messages.error(request, "Нет игроков для старта игры")
            return redirect("game:detail", game_id=game.game_id)

        game.start_game()
        return redirect("game:detail", game_id=game.game_id)


class ApplyStressTestView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        game = get_object_or_404(
            Game, game_id=kwargs["game_id"], creator=request.user
        )
        scenario_id = request.POST.get("scenario_id")
        scenario = get_object_or_404(Scenario, id=scenario_id)

        impacts = {}
        explanations = {}

        for impact in scenario.impacts.select_related("stock").all():
            impacts[impact.stock.ticker] = float(impact.coefficient)
            explanations[impact.stock.ticker] = impact.explanation

        results = []
        for player in game.players.all():
            old_value = player.total_value
            new_value = player.calculate_total_value(impacts)
            change = new_value - old_value
            change_percent = (change / old_value * 100) if old_value > 0 else 0

            results.append(
                {
                    "player_name": player.player_name,
                    "old_value": float(old_value),
                    "new_value": float(new_value),
                    "change": float(change),
                    "change_percent": float(change_percent),
                }
            )

        request.session["stress_test_results"] = {
            "scenario_name": scenario.name,
            "results": results,
            "explanations": explanations,
        }

        game.finish_game()

        return redirect("game:results", game_id=game.game_id)


class GameResultsView(TemplateView):
    template_name = "game/results.html"

    def dispatch(self, request, *args, **kwargs):
        self.game = get_object_or_404(Game, game_id=kwargs["game_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        stress_results = self.request.session.get("stress_test_results")

        ranking = self.game.players.filter(final_value__isnull=False).order_by(
            "-final_value"
        )

        for i, player in enumerate(ranking, 1):
            player.rank = i
            player.save(update_fields=["rank"])

        stock_changes = []
        if stress_results and "explanations" in stress_results:
            for ticker, explanation in stress_results["explanations"].items():
                try:
                    stock = Stock.objects.get(ticker=ticker)
                    stock_changes.append(
                        {
                            "ticker": ticker,
                            "name": stock.name,
                            "explanation": explanation,
                        }
                    )
                except Stock.DoesNotExist:
                    pass

        context.update(
            {
                "game": self.game,
                "ranking": ranking,
                "stress_results": stress_results,
                "stock_changes": stock_changes,
            }
        )

        return context


class GameTradeMixin:
    def _get_player(self, request, game):
        if request.user.is_authenticated:
            return GamePlayer.objects.get(game=game, user=request.user)
        else:
            player_name = request.session.get("game_player_name")
            return GamePlayer.objects.get(game=game, player_name=player_name)

    def _validate(self, request, game, quantity):
        if quantity <= 0:
            return {"error": "Неверное количество"}

        if game.status != "active":
            return {"error": "Игра не активна"}

        return None


class GameBuyView(View, GameTradeMixin):
    def post(self, request, *args, **kwargs):
        game = get_object_or_404(Game, game_id=kwargs["game_id"])

        try:
            player = self._get_player(request, game)
        except GamePlayer.DoesNotExist:
            return JsonResponse({"error": "Игрок не найден"}, status=404)

        ticker = request.POST.get("ticker")
        quantity = int(request.POST.get("quantity", 0))

        error = self._validate(request, game, quantity)
        if error:
            return JsonResponse(error, status=400)

        stock = get_object_or_404(Stock, ticker=ticker)

        try:
            with transaction.atomic():
                player.buy_stock(stock, quantity)
            return JsonResponse(
                {
                    "success": True,
                    "cash": float(player.cash),
                    "total_value": float(player.total_value),
                    "quantity": quantity,
                    "stock_ticker": stock.ticker,
                    "stock_name": stock.name,
                }
            )
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)


class GameSellView(View, GameTradeMixin):
    def post(self, request, *args, **kwargs):
        game = get_object_or_404(Game, game_id=kwargs["game_id"])

        try:
            player = self._get_player(request, game)
        except GamePlayer.DoesNotExist:
            return JsonResponse({"error": "Игрок не найден"}, status=404)

        ticker = request.POST.get("ticker")
        quantity = int(request.POST.get("quantity", 0))

        error = self._validate(request, game, quantity)
        if error:
            return JsonResponse(error, status=400)

        stock = get_object_or_404(Stock, ticker=ticker)

        try:
            with transaction.atomic():
                player.sell_stock(stock, quantity)
            return JsonResponse(
                {
                    "success": True,
                    "cash": float(player.cash),
                    "total_value": float(player.total_value),
                    "quantity": quantity,
                    "stock_ticker": stock.ticker,
                    "stock_name": stock.name,
                }
            )
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)


class GamePortfolioView(View):
    def get(self, request, *args, **kwargs):
        game = get_object_or_404(Game, game_id=kwargs["game_id"])

        try:
            if request.user.is_authenticated:
                player = GamePlayer.objects.get(game=game, user=request.user)
            else:
                player_name = request.session.get("game_player_name")
                if not player_name:
                    return JsonResponse(
                        {"error": "Игрок не найден"}, status=404
                    )
                player = GamePlayer.objects.get(
                    game=game, player_name=player_name
                )
        except GamePlayer.DoesNotExist:
            return JsonResponse({"error": "Игрок не найден"}, status=404)

        player.update_total_value()

        holdings_data = []
        for holding in player.holdings.select_related("stock").all():
            holdings_data.append(
                {
                    "ticker": holding.stock.ticker,
                    "name": holding.stock.name,
                    "quantity": holding.quantity,
                    "price": float(holding.stock.last_price),
                    "value": float(holding.current_value),
                }
            )

        return JsonResponse(
            {
                "cash": float(player.cash),
                "total_value": float(player.total_value),
                "holdings": holdings_data,
            }
        )
