import io
from pathlib import Path

import pandas as pd
import pytest
from django.core.management import call_command

from apps.legal_graphrag.models import CorpusSource

pytestmark = pytest.mark.django_db


def base_row(**overrides):
    data = {
        'Prioridad': 'P1',
        'Naturaleza': 'Normativa',
        'Área principal': 'Fiscalidad',
        'Norma / fuente (título resumido)': 'Ley de prueba',
        'Tipo': 'Ley',
        'Ámbito': 'Estatal',
        'Función en ARTISTING': 'Cobertura',
        'ID oficial': 'LAW-1',
        'URL oficial': 'https://example.com/law',
        'Vigencia': 'Vigente',
        'Nivel de autoridad': 'Alta',
        'Artículos clave/alcance': '1-3',
        'Frecuencia de actualización': 'Anual',
    }
    data.update(overrides)
    return data


def write_excel(tmp_path: Path, rows):
    df = pd.DataFrame(rows)
    path = tmp_path / 'corpus.xlsx'
    df.to_excel(path, index=False)
    return path


def test_command_imports_expected_sources(tmp_path):
    rows = [
        base_row(
            **{
                'Norma / fuente (título resumido)': 'Constitución española',
                'ID oficial': 'CONST-1',
            }
        ),
        base_row(
            Prioridad='P2',
            **{
                'Área principal': 'Laboral',
                'Norma / fuente (título resumido)': 'Estatuto de los Trabajadores',
                'ID oficial': 'LAB-1',
            },
        ),
    ]
    excel_path = write_excel(tmp_path, rows)

    stdout = io.StringIO()
    call_command('import_corpus_from_excel', str(excel_path), stdout=stdout)

    assert CorpusSource.objects.count() == 2
    assert CorpusSource.objects.get(id_oficial='CONST-1').titulo == 'Constitución española'
    assert CorpusSource.objects.get(id_oficial='LAB-1').prioridad == 'P2'


def test_update_or_create_prevents_duplicates(tmp_path):
    CorpusSource.objects.create(
        prioridad='P1',
        naturaleza='Normativa',
        area_principal='Fiscal',
        titulo='Ley anterior',
        tipo='Ley',
        ambito='Estatal',
        funcion_artisting='Histórico',
        id_oficial='LAW-42',
        url_oficial='https://example.com/old',
    )

    excel_path = write_excel(
        tmp_path,
        [
            base_row(
                **{
                    'Norma / fuente (título resumido)': 'Ley actualizada',
                    'ID oficial': 'LAW-42',
                    'URL oficial': 'https://example.com/new',
                }
            )
        ],
    )

    call_command('import_corpus_from_excel', str(excel_path))

    assert CorpusSource.objects.count() == 1
    refreshed = CorpusSource.objects.get(id_oficial='LAW-42')
    assert refreshed.titulo == 'Ley actualizada'
    assert refreshed.url_oficial == 'https://example.com/new'


def test_missing_columns_are_handled(tmp_path):
    rows = [
        {
            'Prioridad': 'P3',
            'Naturaleza': 'Guía',
            'Norma / fuente (título resumido)': 'Guía fiscal',
            'Función en ARTISTING': 'Referencia',
            'ID oficial': 'GUIDE-1',
            'URL oficial': 'https://example.com/guide',
        }
    ]
    excel_path = write_excel(tmp_path, rows)

    call_command('import_corpus_from_excel', str(excel_path))

    source = CorpusSource.objects.get(id_oficial='GUIDE-1')
    assert source.frecuencia_actualizacion is None
    assert source.area_principal is None
