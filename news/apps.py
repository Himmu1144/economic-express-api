from django.apps import AppConfig


class NewsConfig(AppConfig):
    name = "news"

    def ready(self):
        from . import signals, checks  # noqa: F401 -- register handlers and checks
