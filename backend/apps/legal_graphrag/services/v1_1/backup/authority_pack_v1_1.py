"""
V1.1 Authority Pack
Loads the enriched Excel once and builds synthetic sources for meta-legal questions.
"""

from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd


_COLUMN_ALIASES = {
    "prioridad": ["Prioridad"],
    "naturaleza": ["Naturaleza"],
    "area_principal": ["Área principal", "Ç?rea principal"],
    "titulo": ["Norma / fuente (título resumido)", "Norma / fuente (tÇðtulo resumido)"],
    "tipo": ["Tipo"],
    "ambito": ["Ámbito", "Ç?mbito"],
    "funcion_artisting": ["Función en ARTISTING", "FunciÇün en ARTISTING"],
    "id_oficial": ["ID oficial"],
    "url_oficial": ["URL oficial"],
    "vigencia": ["Vigencia"],
    "nivel_autoridad": ["Nivel de autoridad"],
    "articulos_clave": ["Artículos clave/alcance", "ArtÇðculos clave/alcance"],
    "frecuencia_actualizacion": ["Frecuencia de actualización", "Frecuencia de actualizaciÇün"],
}


def _to_ascii(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _norm(text: str) -> str:
    return _to_ascii(text or "").lower()


def _first_existing_path() -> Optional[Path]:
    env_path = os.getenv("LEGAL_AUTHORITY_XLSX_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    root = Path(__file__).resolve().parents[5]
    candidates = [
        root / "corpus_normativo_artisting_enriched_clean.xlsx",
        root / "corpus_normativo_artisting_enriched.xlsx",
        root / "corpus" / "corpus_normativo_artisting_enriched.xlsx",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _get_column(df: pd.DataFrame, keys: List[str]) -> Optional[str]:
    for key in keys:
        if key in df.columns:
            return key
    return None


@lru_cache(maxsize=1)
def load_authority_rows() -> List[Dict[str, Any]]:
    path = _first_existing_path()
    if not path:
        return []

    df = pd.read_excel(path)

    columns = {}
    for field, aliases in _COLUMN_ALIASES.items():
        col = _get_column(df, aliases)
        columns[field] = col

    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        item = {}
        for field, col in columns.items():
            value = row[col] if col else None
            if pd.isna(value):
                value = None
            if isinstance(value, str):
                value = value.strip() or None
            item[field] = value
        if not item.get("titulo"):
            continue
        rows.append(item)
    return rows


def is_authority_question(query: str) -> bool:
    q = _norm(query)
    if not q:
        return False
    triggers = [
        "jerarquia", "rango", "norma superior", "norma prevalece",
        "fuentes del derecho", "fuentes de derecho", "rango juridico",
        "contradecir", "reglamento vs", "reglamento contra", "reglamento contradice",
        "ley organica", "ley ordinaria", "constitucion", "aplica la ley",
        "aplicacion de la ley", "procedimiento administrativo", "ley 39/2015",
        "principio de jerarquia normativa",
    ]
    return any(tok in q for tok in triggers)


def _row_matches(row: Dict[str, Any], needle: str) -> bool:
    haystack = " ".join([
        str(row.get("titulo") or ""),
        str(row.get("id_oficial") or ""),
        str(row.get("tipo") or ""),
        str(row.get("nivel_autoridad") or ""),
        str(row.get("ambito") or ""),
        str(row.get("articulos_clave") or ""),
        str(row.get("funcion_artisting") or ""),
    ])
    return _norm(needle) in _norm(haystack)


def _pick_first(rows: List[Dict[str, Any]], predicate) -> Optional[Dict[str, Any]]:
    for row in rows:
        if predicate(row):
            return row
    return None


def _make_source(row: Dict[str, Any]) -> Dict[str, Any]:
    parts = []
    if row.get("prioridad"):
        parts.append(f"Prioridad: {row['prioridad']}")
    if row.get("nivel_autoridad"):
        parts.append(f"Nivel de autoridad: {row['nivel_autoridad']}")
    if row.get("ambito"):
        parts.append(f"Ámbito: {row['ambito']}")
    if row.get("vigencia"):
        parts.append(f"Vigencia: {row['vigencia']}")
    if row.get("funcion_artisting"):
        parts.append(f"Función en ARTISTING: {row['funcion_artisting']}")
    if row.get("articulos_clave"):
        parts.append(f"Artículos clave/alcance: {row['articulos_clave']}")
    if row.get("frecuencia_actualizacion"):
        parts.append(f"Frecuencia de actualización: {row['frecuencia_actualizacion']}")

    chunk_text = ". ".join(parts)
    naturaleza = row.get("naturaleza") or "Normativa"

    return {
        "source_naturaleza": naturaleza,
        "document_id": row.get("id_oficial") or row.get("titulo"),
        "document_title": row.get("titulo") or "Fuente sin título",
        "document_url": row.get("url_oficial") or "",
        "chunk_label": "Ficha autoridad (Excel)",
        "chunk_text": chunk_text,
        "rrf_score": 9999,
        "similarity": 1.0,
        "source": "authority_pack_excel",
    }


def build_authority_sources(query: str, area: Optional[str]) -> Dict[str, List[Dict[str, Any]]]:
    rows = load_authority_rows()
    buckets = {"normativa": [], "doctrina": [], "jurisprudencia": []}
    if not rows:
        return buckets

    q = _norm(query)
    const_row = _pick_first(
        rows,
        lambda r: (r.get("prioridad") == "P1") and _row_matches(r, "constitucion"),
    )

    def add_row(row: Optional[Dict[str, Any]]) -> None:
        if not row:
            return
        source = _make_source(row)
        naturaleza = (row.get("naturaleza") or "").lower()
        if "doctrina" in naturaleza:
            buckets["doctrina"].append(source)
        elif "jurisprud" in naturaleza:
            buckets["jurisprudencia"].append(source)
        else:
            buckets["normativa"].append(source)

    if any(tok in q for tok in ["jerarquia", "rango", "norma superior", "fuentes del derecho", "rango juridico"]):
        add_row(const_row)

    if ("reglamento" in q and "ley" in q) or "contradecir" in q:
        add_row(const_row)
        ley_row = _pick_first(rows, lambda r: r.get("prioridad") == "P1" and _row_matches(r, "ley"))
        reglamento_row = _pick_first(
            rows,
            lambda r: r.get("prioridad") == "P1" and (
                _row_matches(r, "reglamento") or _row_matches(r, "real decreto")
            ),
        )
        add_row(ley_row)
        add_row(reglamento_row)

    if "ley 39/2015" in q:
        ley_39_row = _pick_first(rows, lambda r: _row_matches(r, "39/2015"))
        if ley_39_row:
            add_row(ley_39_row)
        else:
            procedimiento_row = _pick_first(
                rows,
                lambda r: r.get("prioridad") == "P1" and _row_matches(r, "procedimiento administrativo"),
            )
            add_row(procedimiento_row)

    if "ley organica" in q or "ley ordinaria" in q:
        add_row(const_row)
        organica_row = _pick_first(rows, lambda r: r.get("prioridad") == "P1" and _row_matches(r, "ley organica"))
        ordinaria_row = _pick_first(rows, lambda r: r.get("prioridad") == "P1" and _row_matches(r, "ley ordinaria"))
        add_row(organica_row)
        add_row(ordinaria_row)

    # General fallback: if still empty, add a high-authority normativa row in the same area.
    if not any(buckets.values()):
        area_norm = _norm(area or "")
        area_row = _pick_first(
            rows,
            lambda r: r.get("prioridad") == "P1" and (not area_norm or _row_matches(r, area_norm)),
        )
        add_row(area_row)

    return buckets
