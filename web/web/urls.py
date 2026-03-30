import django.conf.urls.static
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("apps.homepage.urls")),
    path("users/", include("apps.users.urls")),
    path("admin/", admin.site.urls),
]

urlpatterns += django.conf.urls.static.static(
    settings.STATIC_URL,
    document_root=settings.STATIC_ROOT,
)

urlpatterns += django.conf.urls.static.static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT,
)
