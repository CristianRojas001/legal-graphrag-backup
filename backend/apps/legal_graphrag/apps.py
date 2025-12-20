from django.apps import AppConfig


class LegalGraphragConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.legal_graphrag'
    verbose_name = 'Legal GraphRAG'

    def ready(self):
        """Import signals when the app is ready."""
        pass
