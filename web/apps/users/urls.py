from apps.users import views

from django.urls import path

app_name = "users"
urlpatterns = [
    path(
        "login/",
        views.UserLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        views.UserLogoutView.as_view(),
        name="logout",
    ),
    path(
        "profile/",
        views.ProfileView.as_view(),
        name="profile",
    ),
    path(
        "profile/edit/",
        views.ProfileEditView.as_view(),
        name="profile_edit",
    ),
]
