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
from django.views.generic import TemplateView, UpdateView


class UserLoginView(LoginView):
    form_class = CustomAuthenticationForm
    template_name = "users/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        auth_type = request.POST.get("auth_type")

        if auth_type == "register":
            register_form = CustomUserCreationForm(request.POST)
            if register_form.is_valid():
                user = register_form.save()
                login(request, user)
                return redirect(self.get_success_url())
            else:
                return self.render_to_response(
                    self.get_context_data(register_form=register_form),
                )

        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "register_form" not in context:
            context["register_form"] = CustomUserCreationForm()

        return context

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

    def post(self, request, *args, **kwargs):
        if "delete_avatar" in request.POST:
            user = self.get_object()
            if user.image:
                user.image.delete(save=False)
                user.image = None
                user.save()
                messages.success(request, "Аватар удалён")
            else:
                messages.warning(request, "Аватар не был установлен")

            return redirect(self.get_success_url())

        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("users:profile")
