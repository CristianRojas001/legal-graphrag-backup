"""
Deterministic tax rate resolver for IVA/IRPF based on local JSON tables.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional


_DATA_CACHE: Dict[str, Dict[str, Any]] = {}


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _get_data_path(*parts: str) -> Path:
    base_dir = Path(__file__).resolve().parents[4]  # backend/
    return base_dir.joinpath("data", "aeat", *parts)


def _dataset(name: str) -> Dict[str, Any]:
    cached = _DATA_CACHE.get(name)
    if cached is not None:
        return cached
    if name == "iva":
        path = _get_data_path("iva", "tipos_iva_2025_core.json")
    elif name == "irpf":
        path = _get_data_path("irpf", "retenciones_irpf_2026_core.json")
    else:
        raise ValueError(f"Unknown dataset: {name}")
    data = _load_json(path)
    _DATA_CACHE[name] = data
    return data


def extract_percentages(answer_text: str) -> List[int]:
    if not answer_text:
        return []
    matches = re.findall(r"\b(\d{1,3})\s*%", answer_text)
    return [int(value) for value in matches if value.isdigit()]


def sanitize_answer_percentages(
    answer_text: str,
    allowed_percentages: Optional[List[int]],
    non_tax_allowlist: Optional[List[int]] = None,
) -> Dict[str, Any]:
    allowed = {int(value) for value in (allowed_percentages or [])}
    if non_tax_allowlist:
        allowed.update(int(value) for value in non_tax_allowlist)
    found = extract_percentages(answer_text)
    disallowed = [value for value in found if value not in allowed]
    if not disallowed:
        return {"text": answer_text, "changed": False, "disallowed": []}

    def replace_match(match: re.Match) -> str:
        value = match.group(1)
        try:
            number = int(value)
        except ValueError:
            return match.group(0)
        if number in allowed:
            return match.group(0)
        return "[porcentaje omitido]"

    sanitized = re.sub(r"\b(\d{1,3})\s*%", replace_match, answer_text)
    notice = (
        "\n\nNota: He omitido porcentajes no verificados por el resolver "
        "deterministico de IVA/IRPF."
    )
    if notice not in sanitized:
        sanitized = sanitized.rstrip() + notice
    return {"text": sanitized, "changed": True, "disallowed": disallowed}


class TaxRateResolver:
    def __init__(self) -> None:
        self._iva = _dataset("iva")
        self._irpf = _dataset("irpf")
        self._iva_synonyms = self._build_iva_synonyms()

    @staticmethod
    def _build_iva_synonyms() -> Dict[str, List[str]]:
        raw_synonyms = {
            "entrada": ["ticket", "tickets", "boleto", "boletos", "pase", "pases"],
            "teatro": ["teatral", "teatrales", "obra teatral", "produccion teatral"],
            "concierto": ["recital", "recitales", "festival", "festivales"],
            "museo": ["museos", "exposicion", "exposiciones"],
            "biblioteca": ["bibliotecas"],
            "interprete": ["interpretes", "interpretacion", "interpretaciones"],
            "artista": ["artistas", "artistico", "artistica", "artisticos", "artisticas"],
            "director": ["directora", "direccion", "direccion tecnica", "direccion artistica"],
            "tecnico": ["tecnica", "tecnicos", "tecnicas", "tecnico de escena", "tecnico de sonido"],
            "organizador": ["organizadores", "organizacion", "promotor", "promotora", "productor", "productora"],
            "productor de cine": ["productor cinematografico", "productora cinematografica", "produccion cinematografica"],
            "hosteleria": ["restauracion", "restaurante", "restaurantes", "bar", "bares", "cafeteria", "cafeterias"],
            "acampamento": ["campamento", "campamentos", "camping"],
            "balneario": ["spa", "termas"],
            "discoteca": ["discotecas", "sala de fiesta", "salas de fiesta", "pub", "club"],
            "barbacoa": ["barbacoas"],
            "comidas": ["comida", "catering"],
            "bebidas": ["bebida"],
            "periodico": ["diario", "diarios"],
        }
        normalized: Dict[str, List[str]] = {}
        for canonical, synonyms in raw_synonyms.items():
            canonical_norm = _normalize_text(canonical)
            normalized_syns = []
            for synonym in synonyms:
                synonym_norm = _normalize_text(synonym)
                if synonym_norm and synonym_norm != canonical_norm:
                    normalized_syns.append(synonym_norm)
            if canonical_norm:
                normalized[canonical_norm] = list(dict.fromkeys(normalized_syns))
        return normalized

    def resolve_iva(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        keywords = intent.get("keywords") or []
        topic = intent.get("topic") or "unknown"
        normalized_keywords = self._expand_keywords(keywords)

        for entry in self._iva.get("entries", []):
            match = entry.get("match") or {}
            if match.get("kind") != "keyword_any":
                continue
            if self._keyword_any_match(match.get("keywords_any") or [], normalized_keywords):
                return self._build_ok(entry)

        topic_map = {
            "entradas_cultura": "IVA_ENTRADAS_CULTURA",
            "servicios_artistas": "IVA_SERVICIOS_ARTISTAS_A_ORGANIZADOR",
            "libros_prensa": "IVA_LIBROS_PRENSA_REVISTAS",
            "general": "IVA_GENERAL",
        }
        if topic in topic_map:
            entry = self._find_entry_by_id(self._iva, topic_map[topic])
            if entry:
                return self._build_ok(entry)

        fallback = self._find_fallback(self._iva)
        if fallback:
            return self._build_ok(fallback)
        return {"status": "error", "message": "IVA dataset missing fallback"}

    def resolve_irpf(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        income_type = intent.get("income_type") or "unknown"
        new_activity = intent.get("new_activity")
        turnover = intent.get("net_turnover_bucket")

        if income_type == "unknown" or not income_type:
            return self._needs_clarification(
                ["income_type"],
                "Tu caso es (A) actividad profesional o (B) consejero/administrador? "
                "Si es cesion de derecho de imagen o arrendamiento urbano, indicalo.",
            )

        if income_type == "consejero_administrador" and turnover is None:
            return self._needs_clarification(
                ["net_turnover_bucket"],
                "La cifra de negocios supera 100.000 EUR? (A) Si (B) No",
            )

        if income_type == "actividad_profesional" and new_activity is None:
            return self._needs_clarification(
                ["new_activity"],
                "Es inicio de actividad (menos de 3 anos)? (A) Si (B) No",
            )

        for entry in self._irpf.get("entries", []):
            match = entry.get("match") or {}
            if match.get("kind") != "all":
                continue
            conditions = match.get("conditions") or {}
            if self._conditions_match(conditions, income_type, new_activity, turnover):
                return self._build_ok(entry)

        return self._needs_clarification(
            ["income_type"],
            "No puedo determinar el tipo IRPF con la informacion actual. "
            "Tu caso es (A) actividad profesional o (B) consejero/administrador?",
        )

    @staticmethod
    def _keyword_any_match(keywords_any: List[str], normalized_keywords: set[str]) -> bool:
        if not keywords_any:
            return False
        for keyword in keywords_any:
            if _normalize_text(keyword) in normalized_keywords:
                return True
        return False

    def _expand_keywords(self, keywords: List[str]) -> set[str]:
        normalized = {_normalize_text(word) for word in keywords if word}
        expanded = set(normalized)
        expanded.update(self._expand_plural_variants(expanded))
        expanded.update(self._expand_with_synonyms(expanded))
        return expanded

    @staticmethod
    def _expand_plural_variants(tokens: set[str]) -> set[str]:
        variants = set()
        for token in tokens:
            if len(token) <= 3:
                continue
            if token.endswith("es") and len(token) > 4:
                variants.add(token[:-2])
            if token.endswith("s"):
                variants.add(token[:-1])
        return variants

    def _expand_with_synonyms(self, tokens: set[str]) -> set[str]:
        expanded = set(tokens)
        for canonical, synonyms in self._iva_synonyms.items():
            if canonical in expanded:
                continue
            if any(synonym in expanded for synonym in synonyms):
                expanded.add(canonical)
        return expanded

    @staticmethod
    def _conditions_match(
        conditions: Dict[str, Any],
        income_type: str,
        new_activity: Any,
        turnover: Any,
    ) -> bool:
        if conditions.get("income_type") and conditions["income_type"] != income_type:
            return False
        if "new_activity" in conditions and conditions["new_activity"] != new_activity:
            return False
        if "net_turnover_bucket" in conditions and conditions["net_turnover_bucket"] != turnover:
            return False
        return True

    @staticmethod
    def _find_entry_by_id(dataset: Dict[str, Any], entry_id: str) -> Optional[Dict[str, Any]]:
        for entry in dataset.get("entries", []):
            if entry.get("id") == entry_id:
                return entry
        return None

    @staticmethod
    def _find_fallback(dataset: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for entry in dataset.get("entries", []):
            match = entry.get("match") or {}
            if match.get("kind") == "fallback_general":
                return entry
        return None

    @staticmethod
    def _build_ok(entry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "ok",
            "rate_percent": entry.get("rate_percent"),
            "rule_id": entry.get("id"),
            "refs": entry.get("refs", []),
        }

    @staticmethod
    def _needs_clarification(missing_fields: List[str], question: str) -> Dict[str, Any]:
        return {
            "status": "needs_clarification",
            "missing_fields": missing_fields,
            "clarifying_question": question,
        }
