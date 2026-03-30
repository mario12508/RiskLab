__all__ = ()

from apps.users.forms import (
    CustomAuthenticationForm,
    CustomUserCreationForm,
    UserProfileForm,
)

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, TemplateView, UpdateView


class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = "users/register.html"
    success_url = reverse_lazy("homepage:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.save()
        login(self.request, user)
        return response

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("homepage:home")

        return super().dispatch(request, *args, **kwargs)


class UserLoginView(LoginView):
    form_class = CustomAuthenticationForm
    template_name = "users/login.html"
    redirect_authenticated_user = True

    def form_invalid(self, form):
        messages.error(self.request, "Неверное имя пользователя или пароль")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy("homepage:home")


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("homepage:home")


@method_decorator(login_required, name="dispatch")
class ProfileView(TemplateView):
    template_name = "users/profile.html"


@method_decorator(login_required, name="dispatch")
class ProfileEditView(UpdateView):
    form_class = UserProfileForm
    template_name = "users/profile_edit.html"

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse_lazy("users:profile")
