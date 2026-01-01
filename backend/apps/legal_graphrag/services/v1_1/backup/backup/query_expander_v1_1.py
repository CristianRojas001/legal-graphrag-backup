"""
V1.1 Query Expander
Deterministic expansions + limited LLM variants.
"""

import re
import unicodedata
from collections import OrderedDict
import hashlib
from typing import List


class QueryExpanderV1_1:
    def __init__(self, model) -> None:
        self.model = model
        self._expansion_cache: "OrderedDict[str, List[str]]" = OrderedDict()
        self._cache_max_size = 500

    @staticmethod
    def _to_ascii(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        return "".join(ch for ch in normalized if not unicodedata.combining(ch))

    def _cache_key(self, query: str, max_total: int, llm_variants: int) -> str:
        normalized = self._to_ascii((query or "").lower().strip())
        key = f"{normalized}:{max_total}:{llm_variants}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> List[str]:
        payload = self._expansion_cache.get(key)
        if payload is None:
            return []
        self._expansion_cache.move_to_end(key)
        return list(payload)

    def _cache_set(self, key: str, queries: List[str]) -> None:
        self._expansion_cache[key] = list(queries)
        self._expansion_cache.move_to_end(key)
        while len(self._expansion_cache) > self._cache_max_size:
            self._expansion_cache.popitem(last=False)

    def _add(self, queries: List[str], value: str) -> None:
        value = (value or "").strip()
        if value and value not in queries:
            queries.append(value)

    def expand(self, query: str, max_total: int = 8, llm_variants: int = 3) -> List[str]:
        """
        Expand a query with deterministic patterns and limited LLM variants.
        Returns a de-duplicated list of queries.
        """
        base = (query or "").strip()
        if not base:
            return []

        cache_key = self._cache_key(base, max_total, llm_variants)
        cached = self._cache_get(cache_key)
        if cached:
            return cached[:max_total]

        queries: List[str] = []
        self._add(queries, base)

        # Keep unicode for search, only normalize for pattern matching below
        ascii_query = self._to_ascii(base)

        # BOE ID patterns
        boe_match = re.search(r"(BOE[-\\s]?A-\\d{4}-\\d+)", ascii_query, flags=re.IGNORECASE)
        if boe_match:
            boe_id = boe_match.group(1).upper().replace(" ", "")
            self._add(queries, boe_id)
            self._add(queries, f"BOE {boe_id}")

        # Law number patterns
        law_match = re.search(r"(Ley\\s+\\d+/\\d{4})", ascii_query, flags=re.IGNORECASE)
        if law_match:
            law_ref = law_match.group(1)
            self._add(queries, law_ref)
            self._add(queries, f"{law_ref} objeto")

        # Targeted expansions for hierarchy-style questions (with proper accents)
        if "constitucion" in ascii_query.lower():
            self._add(queries, "Constitución española")
        if "jerarquia" in ascii_query.lower() or "rango juridico" in ascii_query.lower():
            self._add(queries, "Constitución española jerarquía normativa")
        if "directiva" in ascii_query.lower():
            self._add(queries, "Directiva europea transposición ley española")
        if "reglamento europeo" in ascii_query.lower():
            self._add(queries, "Reglamento europeo primacía")
        if "ley organica" in ascii_query.lower():
            self._add(queries, "Ley Orgánica requisitos")
        if "subvencion" in ascii_query.lower():
            self._add(queries, "Ley 38/2003 subvenciones")
        if "jerarquia" in ascii_query.lower() or "rango" in ascii_query.lower():
            self._add(queries, "principio de jerarquía normativa")
            self._add(queries, "fuentes del derecho español")
            self._add(queries, "rango reglamento vs ley")
            self._add(queries, "Constitución jerarquía normativa")
            self._add(queries, "norma suprema Constitución")
            self._add(queries, "reglamento no puede contradecir ley")

        # Common IVA/tax queries
        if "iva" in ascii_query.lower():
            self._add(queries, "IVA tipos impositivos")
            self._add(queries, "Ley 37/1992 IVA")
        if "tipo" in ascii_query.lower() and "iva" in ascii_query.lower():
            self._add(queries, "tipos IVA general reducido superreducido")
        if "retencion" in ascii_query.lower() or "retenciones" in ascii_query.lower():
            self._add(queries, "retenciones IRPF")
            self._add(queries, "tipos retención")
        if "amortiz" in ascii_query.lower():
            self._add(queries, "amortizacion IRPF")
            self._add(queries, "Ley 35/2006 IRPF amortizacion")

        # Services/digital
        if "servicio" in ascii_query.lower() or "digital" in ascii_query.lower():
            self._add(queries, "servicios digitales IVA")
            self._add(queries, "prestación servicios")

        # Artists/cultural
        if "artista" in ascii_query.lower() or "cultural" in ascii_query.lower():
            self._add(queries, "artistas profesionales")
            self._add(queries, "actividades artísticas")

        # LLM variants (bounded)
        if self.model and len(queries) < max_total and llm_variants > 0:
            prompt = f"""Genera hasta {llm_variants} variantes CORTAS de búsqueda legal en español para la pregunta del usuario.

REGLAS:
- No cambies el significado.
- Cada variante: 4–12 palabras.
- Haz variantes que ayuden a recuperar normativa/criterios/jurisprudencia.
- Incluye sinónimos y términos jurídicos cercanos cuando aplique (p.ej., "jerarquía normativa", "fuentes del derecho").
- Si ves patrones (BOE-A-YYYY-NNNN, ECLI:ES:...), crea 1 variante con ese patrón.
- No uses comillas ni explicaciones.

SALIDA:
Devuelve SOLO un JSON array de strings. Ejemplo: ["...", "..."]

Pregunta: {base}"""
            try:
                response = self.model.generate_content(prompt)
                text = (response.text or "").strip()

                items = None
                try:
                    import json

                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        items = parsed
                except Exception:
                    items = None

                if items is None:
                    match = re.search(r"\[[\s\S]*?\]", text)
                    if match:
                        try:
                            import json

                            parsed = json.loads(match.group(0))
                            if isinstance(parsed, list):
                                items = parsed
                        except Exception:
                            items = None

                if items:
                    for item in items:
                        if len(queries) >= max_total:
                            break
                        if isinstance(item, str):
                            # Keep unicode/accents in LLM variants
                            self._add(queries, item.strip())
            except Exception:
                # Ignore LLM expansion errors
                pass

        final_queries = queries[:max_total]
        self._cache_set(cache_key, final_queries)
        return final_queries

