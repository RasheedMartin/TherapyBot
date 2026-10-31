from django.apps import AppConfig


class TherapybotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'therapybot'

    def ready(self):
        from therapybot import signals  # noqa: F401  (connects receivers)
