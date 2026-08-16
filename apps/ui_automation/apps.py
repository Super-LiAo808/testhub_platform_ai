from django.apps import AppConfig


class UiAutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ui_automation'
    verbose_name = 'UI自动化测试'

    def ready(self):
        # Register auto-diagnose signals
        from . import signals  # noqa: F401