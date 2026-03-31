__all__ = ()

import django.views.generic


class Home(django.views.generic.TemplateView):
    template_name = "homepage/home.html"
