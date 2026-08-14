# -*- coding: utf-8 -*-
from django.apps import AppConfig


class AppAutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.app_automation'
    verbose_name = 'APP自动化测试'

    def ready(self):
        """应用启动时执行"""
        try:
            import apps.app_automation.tasks  # noqa
        except ImportError:
            pass
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
