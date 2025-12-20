from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
import pandas as pd

from apps.legal_graphrag.models import CorpusSource

COLUMN_MAP = {
    'Prioridad': 'prioridad',
    'Naturaleza': 'naturaleza',
    'Área principal': 'area_principal',
    'Norma / fuente (título resumido)': 'titulo',
    'Tipo': 'tipo',
    'Ámbito': 'ambito',
    'Función en ARTISTING': 'funcion_artisting',
    'ID oficial': 'id_oficial',
    'URL oficial': 'url_oficial',
    'Vigencia': 'vigencia',
    'Nivel de autoridad': 'nivel_autoridad',
    'Artículos clave/alcance': 'articulos_clave',
    'Frecuencia de actualización': 'frecuencia_actualizacion',
}
VALID_PRIORIDADES = {choice for choice, _ in CorpusSource.PRIORIDAD_CHOICES}


class Command(BaseCommand):
    help = 'Import corpus sources from Excel file'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to Excel file')

    def handle(self, *args, **options):
        excel_path = options['excel_file']

        try:
            df = pd.read_excel(excel_path)
        except Exception as exc:  # pragma: no cover - surfaced through CommandError
            raise CommandError(f"Unable to read Excel file '{excel_path}': {exc}") from exc

        missing_columns = [col for col in COLUMN_MAP if col not in df.columns]
        if missing_columns:
            self.stderr.write(
                self.style.WARNING(
                    f"Missing columns in Excel file: {', '.join(missing_columns)}. "
                    "They will be set to empty values."
                )
            )
            for column in missing_columns:
                df[column] = None

        imported = 0
        for row_index, row in df.iterrows():
            cleaned_values = {
                model_field: self._clean_value(row[column])
                for column, model_field in COLUMN_MAP.items()
            }
            cleaned_values['prioridad'] = self._coerce_prioridad(cleaned_values.get('prioridad'), row_index)

            id_oficial = cleaned_values['id_oficial']
            titulo = cleaned_values.get('titulo')
            if not titulo:
                self.stderr.write(self.style.WARNING("Skipping row without title information."))
                continue

            if not id_oficial:
                generated_id = self._generate_fallback_id(cleaned_values.get('titulo'), row_index)
                if not generated_id:
                    self.stderr.write(self.style.WARNING("Skipping row without 'ID oficial'."))
                    continue
                id_oficial = generated_id
                self.stderr.write(
                    self.style.WARNING(
                        f"Row {row_index + 1}: generated id_oficial '{id_oficial}' from the title."
                    )
                )

            defaults = cleaned_values.copy()
            defaults.pop('id_oficial')
            defaults['url_oficial'] = defaults.get('url_oficial') or self._build_placeholder_url(id_oficial)

            CorpusSource.objects.update_or_create(
                id_oficial=id_oficial,
                defaults=defaults,
            )
            imported += 1
            titulo = cleaned_values.get('titulo') or id_oficial
            self.stdout.write(f"Imported: {titulo}")

        self.stdout.write(self.style.SUCCESS(f"Imported {imported} sources"))

    @staticmethod
    def _clean_value(value):
        """Normalize Excel cell values into model-friendly Python objects."""
        if pd.isna(value):
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @staticmethod
    def _generate_fallback_id(titulo, row_index):
        if not titulo:
            return None
        slug = slugify(titulo)
        if not slug:
            return None
        return f"auto-{row_index + 1:03d}-{slug[:50]}"

    @staticmethod
    def _build_placeholder_url(id_oficial):
        slug = slugify(id_oficial) or "sin-url"
        return f"https://pending-url.local/{slug}"

    def _coerce_prioridad(self, prioridad, row_index):
        if prioridad in VALID_PRIORIDADES:
            return prioridad
        if prioridad:
            self.stderr.write(
                self.style.WARNING(
                    f"Row {row_index + 1}: prioridad '{prioridad}' is invalid. Defaulting to 'P3'."
                )
            )
        return 'P3'
