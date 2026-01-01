"""
Legal RAG Engine
Orchestrates the entire RAG pipeline: intent classification → hierarchical search → LLM answer generation
"""

import logging
import re
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from django.conf import settings

from apps.legal_graphrag.services.legal_search_engine import LegalSearchEngine
from apps.legal_graphrag.services.intent_classifier import IntentClassifier

logger = logging.getLogger(__name__)


class LegalRAGEngine:
    """
    End-to-end RAG pipeline for legal question answering.

    Pipeline:
    1. Classify user query intent (area_principal)
    2. Retrieve hierarchical sources (normativa → doctrina → jurisprudencia)
    3. Build hierarchical prompt with legal context
    4. Generate answer using Gemini LLM
    5. Format response with citations
    """

    def __init__(self):
        self.search_engine = LegalSearchEngine()
        self.intent_classifier = IntentClassifier()
        self._area_tokens = {
            "Fiscal": [
                "irpf",
                "iva",
                "impuesto",
                "tribut",
                "retencion",
                "retenciones",
                "retener",
                "aeat",
                "dgt",
                "tipo impositivo",
                "base imponible",
            ],
            "Laboral": [
                "seguridad social",
                "reta",
                "autonomo",
                "autónomo",
                "contrato",
                "cotiz",
                "laboral",
            ],
            "Propiedad Intelectual": [
                "propiedad intelectual",
                "derechos de autor",
                "copyright",
                "licencia",
                "obra",
                "reproduccion",
                "distribucion",
                "comunicacion publica",
                "música",
                "musica",
            ],
        }
        # Stronger required terms per area to guard against off-topic sources.
        self._area_required_terms = {
            "Fiscal": ["irpf", "retencion", "retenciones", "iva", "impuesto", "lgt", "aeat", "dgt", "tipo impositivo"],
            "Laboral": ["seguridad social", "reta", "laboral", "autonomo", "aut?nomo", "cotiz", "contrato", "artista", "artistas"],
            "Propiedad Intelectual": ["propiedad intelectual", "derechos de autor", "copyright", "sgae", "cedro", "vegap", "trlpi"],
        }
        # Law-family hints to enforce intent relevance
        self._area_law_hints = {
            "Fiscal": ["irpf", "impuesto sobre la renta", "iva", "impuesto sobre el valor añadido", "retencion", "retenciones", "lgt"],
            "Laboral": ["estatuto de los trabajadores", "seguridad social", "reta", "contrato", "artista", "artistas"],
            "Propiedad Intelectual": ["propiedad intelectual", "trlpi", "derechos de autor"],
        }
        # Abstain thresholds (configurable via settings/env)
        self._min_strict_matches = getattr(settings, "RAG_MIN_STRICT_MATCHES", 1)
        self._min_token_matches = getattr(settings, "RAG_MIN_TOKEN_MATCHES", 1)

        # Configure Gemini API
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=getattr(settings, 'GEMINI_CHAT_MODEL', 'gemini-2.5-flash')
        )

    def answer_query(
        self,
        query: str,
        area_principal: Optional[str] = None,
        max_sources: int = 10
    ) -> Dict[str, Any]:
        """
        Generate a complete answer to a legal query.

        Args:
            query: User's legal question
            area_principal: Optional pre-classified area (if None, will auto-classify)
            max_sources: Maximum number of sources to retrieve

        Returns:
            Dictionary with:
            - answer: Markdown-formatted answer
            - sources: List of source citations
            - metadata: Query metadata (area, model, timing, etc.)
        """
        logger.info(f"RAG query: '{query[:100]}'")

        # Step 1: Classify intent
        if area_principal is None:
            area_classification = self.intent_classifier.classify_with_confidence(query)
            area_principal = area_classification.get('area')
            confidence = area_classification.get('confidence', 0.0)
            logger.info(f"Classified as '{area_principal}' (confidence: {confidence:.2f})")
        else:
            logger.info(f"Using pre-classified area: '{area_principal}'")

        # Step 2: Hierarchical search
        sources = self._retrieve_hierarchical_sources(
            query=query,
            area_principal=area_principal,
            max_sources=max_sources
        )
        sources = self._filter_sources_by_area(area_principal, sources, query)

        # Step 3: Evidence gating (abstain when evidence is weak/off-topic)
        if self._should_abstain(query, area_principal, sources):
            answer_text = self._build_abstain_answer(query)
        else:
            # Step 4: Build prompt
            prompt = self._build_hierarchical_prompt(
                query=query,
                sources=sources,
                area_principal=area_principal
            )

            # Step 5: Generate answer
            try:
                response = self.model.generate_content(prompt)
                answer_text = response.text
                logger.info(f"LLM response generated ({len(answer_text)} chars)")
            except Exception as e:
                logger.error(f"LLM generation failed: {str(e)}")
                answer_text = self._generate_fallback_answer(query, sources)

        # Step 5: Validate, ground, and format response
        answer_text = self._validate_answer(answer_text, sources, area_principal, query)
        answer_text = self._attach_citations(answer_text, sources)
        formatted_sources = self._format_sources(sources)

        return {
            'answer': answer_text,
            'sources': formatted_sources,
            'metadata': {
                'area_principal': area_principal,
                'model': self.model.model_name,
                'normativa_count': len(sources.get('normativa', [])),
                'doctrina_count': len(sources.get('doctrina', [])),
                'jurisprudencia_count': len(sources.get('jurisprudencia', [])),
                'total_sources': len(formatted_sources),
                'abstained': self._should_abstain(query, area_principal, sources),
            }
        }

    def _retrieve_hierarchical_sources(
        self,
        query: str,
        area_principal: Optional[str],
        max_sources: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve sources respecting legal hierarchy:
        1. Normativa P1 (laws, decrees)
        2. Doctrina P1 (administrative guidance)
        3. Jurisprudencia P1/P2 (case law)

        OPTIMIZED: Runs ONE hybrid search and filters results by naturaleza,
        instead of running 3 separate searches (6x faster!)
        """
        sources = {
            'normativa': [],
            'doctrina': [],
            'jurisprudencia': []
        }

        # Run ONE hybrid search to get all relevant sources
        # This is 3x faster than running 3 separate hybrid searches
        try:
            all_results = self.search_engine.hybrid_search(
                query=query,
                limit=max_sources * 2  # Get more results to ensure we have enough after filtering
            )

            # Filter results by naturaleza (hierarchical sorting)
            for result in all_results:
                naturaleza = result.get('source_naturaleza', '')

                if naturaleza == 'Normativa' and len(sources['normativa']) < 5:
                    sources['normativa'].append(result)
                elif naturaleza == 'Doctrina administrativa' and len(sources['doctrina']) < 3:
                    sources['doctrina'].append(result)
                elif naturaleza == 'Jurisprudencia' and len(sources['jurisprudencia']) < 2:
                    sources['jurisprudencia'].append(result)

                # Stop if we have enough sources
                total = len(sources['normativa']) + len(sources['doctrina']) + len(sources['jurisprudencia'])
                if total >= max_sources:
                    break

            logger.info(
                f"Retrieved {len(sources['normativa'])} normativa, "
                f"{len(sources['doctrina'])} doctrina, "
                f"{len(sources['jurisprudencia'])} jurisprudencia sources"
            )

        except Exception as e:
            logger.error(f"Hierarchical search failed: {str(e)}")

        return sources

    def _build_hierarchical_prompt(
        self,
        query: str,
        sources: Dict[str, List[Dict[str, Any]]],
        area_principal: Optional[str]
    ) -> str:
        """
        Build a hierarchical prompt that respects legal authority.

        Prompt structure:
        1. System instructions (hierarchy rules)
        2. Context: Normativa (highest authority)
        3. Context: Doctrina administrativa
        4. Context: Jurisprudencia
        5. User query
        6. Response format instructions
        """
        # Format context sections
        normativa_context = self._format_context_section(
            sources.get('normativa', []),
            section_title="NORMATIVA (Leyes, Reales Decretos, Órdenes)"
        )

        doctrina_context = self._format_context_section(
            sources.get('doctrina', []),
            section_title="DOCTRINA ADMINISTRATIVA (DGT, AEAT, Seguridad Social)"
        )

        jurisprudencia_context = self._format_context_section(
            sources.get('jurisprudencia', []),
            section_title="JURISPRUDENCIA (Tribunal Supremo, TJUE, TEDH)"
        )

        # Build full prompt
        prompt = f"""Eres un asistente legal experto para España (Artisting Legal-RAG). Tu objetivo principal es producir respuestas ÚTILES sin inventar información.

PASO 1: SOURCE TRIAGE (OBLIGATORIO antes de responder)
Clasifica internamente cada fuente proporcionada:
• RELEVANT: Contiene el tema/término legal principal de la pregunta (IRPF, IVA, subvención, justificación, gastos deducibles, afectación) O la ley exacta solicitada (Ley 35/2006, Ley 58/2003, RD 887/2006)
• POSSIBLY RELEVANT: Tema adyacente pero no claramente sobre el término central
• IRRELEVANT: Área diferente (ej: Propiedad Intelectual/Seguridad Social para pregunta de IRPF; IVA régimen especial para pregunta de gastos vivienda)

REGLA DURA: Solo usa fuentes RELEVANT para citas. Si hay CERO fuentes RELEVANT, usa TWO-LANE MODE.

PASO 2: KEYWORD COVERAGE CHECK
Si la pregunta contiene un ancla clave (IRPF, IVA, retenciones, LGT, Ley 38/2003, justificación subvención) pero NINGUNA fuente la menciona:
→ Usa TWO-LANE MODE y di explícitamente: "El corpus recuperado no cubre [tema] para esta pregunta específica"

PASO 3: AUTHORITY MENTION GUARD
Solo menciona una autoridad (DGT, AEAT, Tribunal Supremo, TJUE) si aparece en las fuentes recuperadas.
Si no: usa "orientación general" sin nombrar autoridad.

PASO 4: NUMERIC & RATES RULE
NUNCA declares tasas exactas (21%, 10%, 30%, tipo general) salvo que las fuentes recuperadas contengan ese número explícitamente.
Si el usuario pide una tasa sin evidencia en fuentes:
→ Di que no puedes confirmar la tasa exacta con el corpus actual
→ Explica el concepto (qué factores deciden la tasa)
→ Pregunta 1-2 cosas necesarias para buscar el artículo correcto

MODOS DE RESPUESTA:

A) EVIDENCE-BACKED MODE (usa solo si tienes fuentes RELEVANT):
**Respuesta:**
[2-4 párrafos directos basados en fuentes RELEVANT]

**Fundamento:**
- [Cita fuente RELEVANT 1 con ID]
- [Cita fuente RELEVANT 2 con ID]
[Cada cita debe respaldar una afirmación específica en Respuesta]

**En la práctica:**
[1-2 párrafos aplicación práctica]

B) TWO-LANE MODE (usa cuando evidencia parcial O cero fuentes RELEVANT):
**Lo que sí puedo afirmar con el corpus actual:**
- [Bullet con cita] (solo fuentes RELEVANT)
- [Bullet con cita]

**Orientación general (sin citar, puede requerir verificación):**
[Guía práctica con lenguaje cauteloso: "en general", "a menudo", "suele depender de..."]
[NO uses números/tasas exactas sin evidencia]

**Para afinar:**
- [Pregunta concreta 1 para mejorar búsqueda]
- [Pregunta concreta 2]

C) ABSTAIN MODE (RARO - solo si evidencia débil/faltante Y alto riesgo):
Alto riesgo = porcentajes exactos, plazos, sanciones, criterios vinculantes, elegibilidad subvención
→ Explica qué evidencia tienes (si alguna)
→ Indica qué falta
→ Sugiere info mínima para responder seguro

PREGUNTA DEL USUARIO:
{query}

ÁREA DETECTADA: {area_principal or 'General'}

FUENTES DISPONIBLES:

[NORMATIVA - Leyes y Reglamentos]
{normativa_context}

[DOCTRINA - Criterios administrativos]
{doctrina_context}

[JURISPRUDENCIA - Tribunales]
{jurisprudencia_context}

INSTRUCCIONES FINALES:
1. Haz Source Triage ANTES de escribir (clasifica RELEVANT/POSSIBLY/IRRELEVANT)
2. Si cero fuentes RELEVANT → Two-Lane Mode automáticamente
3. Keyword Coverage: si pregunta menciona IRPF pero ninguna fuente lo cubre → di explícitamente que falta cobertura
4. Cada cita debe "ganarse su lugar" - debe respaldar una afirmación específica
5. No incluyas listas de "Fuentes utilizadas" con fuentes que no citaste en Fundamento
6. Mantén alta tasa de respuesta: Two-Lane Mode > Abstain Mode

FORMATO RESPUESTA (EVIDENCE-BACKED):
- [Cita las fuentes relevantes con IDs]
- [Si usaste conocimiento general, indícalo]

**En la práctica:**
[1-2 párrafos sobre cómo se aplica esto, ejemplos típicos]
"""

        return prompt

    def _validate_answer(
        self,
        answer: str,
        sources: Dict[str, List[Dict[str, Any]]],
        area_principal: Optional[str],
        query: str,
    ) -> str:
        """
        Drop invalid citations and guard numeric claims without support.
        If a risky numeric claim (%, tipo) is not present in the sources, abstain.
        """
        if not answer:
            return answer

        allowed_ids = {src.get('document_id', '') for group in sources.values() for src in group if src.get('document_id')}
        source_text = " ".join([src.get('chunk_text', '') for group in sources.values() for src in group])
        norm_source_text = self._normalize_text(source_text)
        norm_query = self._normalize_text(query)

        # Guard numeric/rate claims: if answer mentions % / "por ciento"/"por 100"/"tipo" without support, abstain
        numeric_patterns = [
            r"\d+[\.,]?\d*\s*%",
            r"\d+[\.,]?\d*\s*por ciento",
            r"\d+[\.,]?\d*\s*por 100",
            r"tipo\s+(impositivo|general|reducido|superreducido)",
        ]
        risky_numeric = any(re.search(p, answer, flags=re.IGNORECASE) for p in [r"\d+%", r"\d+.*por ciento", r"\d+.*por 100", r"tipo"])
        if risky_numeric:
            if not any(re.search(p, norm_source_text, flags=re.IGNORECASE) for p in numeric_patterns):
                return self._build_abstain_answer(query)
            if area_principal == "Fiscal" or "iva" in norm_query:
                allowed_rates = {"0", "4", "5", "10", "21", "0.0", "4.0", "5.0", "10.0", "21.0"}
                found_rates = re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:%|por ciento|por 100)", answer)
                for rate in found_rates:
                    rate_clean = rate.replace(",", ".").rstrip(".")
                    if rate_clean not in allowed_rates:
                        return self._build_abstain_answer(query)
                for rate in found_rates:
                    rate_token = rate.replace(",", ".").rstrip(".")
                    pattern_rate = rf"{re.escape(rate_token)}\s*(%|por ciento|por 100)"
                    if not (re.search(pattern_rate, source_text, flags=re.IGNORECASE) or re.search(pattern_rate, norm_source_text, flags=re.IGNORECASE)):
                        return self._build_abstain_answer(query)
        else:
            # If no risk detected but query mentions IVA and answer mentions a rate, require that rate to exist in sources
            if area_principal == "Fiscal" or "iva" in norm_query:
                found_rates = re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:%|por ciento|por 100)", answer)
                if found_rates:
                    for rate in found_rates:
                        rate_token = rate.replace(",", ".").rstrip(".")
                        pattern_rate = rf"{re.escape(rate_token)}\s*(%|por ciento|por 100)"
                        if not (re.search(pattern_rate, source_text, flags=re.IGNORECASE) or re.search(pattern_rate, norm_source_text, flags=re.IGNORECASE)):
                            return self._build_abstain_answer(query)
                elif not re.search(r"\d+[\.,]?\d*\s*(%|por ciento|por 100)", source_text, flags=re.IGNORECASE):
                    return self._build_abstain_answer(query)

        # Remove citations with IDs not in allowed_ids
        def drop_bad_id(match: re.Match) -> str:
            doc_id = match.group(1).strip()
            return match.group(0) if doc_id in allowed_ids else ""

        answer = re.sub(r"\[ID:\s*([^\]]+)\]", drop_bad_id, answer)
        return answer

    def _format_context_section(
        self,
        chunks: List[Dict[str, Any]],
        section_title: str
    ) -> str:
        """
        Format a list of chunks into a context section for the prompt.
        """
        if not chunks:
            return f"{section_title}:\n(No se encontraron fuentes relevantes en esta categoría)\n"

        context_lines = [f"{section_title}:"]

        for idx, chunk in enumerate(chunks, 1):
            chunk_label = chunk.get('chunk_label', 'Sin etiqueta')
            chunk_text = chunk.get('chunk_text', '')
            doc_title = chunk.get('document_title', 'Documento sin título')
            doc_id = chunk.get('document_id', 'Sin ID')

            context_lines.append(f"\n[Fuente {idx}]: {doc_title} - {chunk_label} ({doc_id})")
            context_lines.append(f"{chunk_text[:800]}...")  # Limit chunk length

        return '\n'.join(context_lines)

    def _attach_citations(
        self,
        answer: str,
        sources: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        Append grounded source list to the answer to avoid off-context citations.
        """
        if not answer:
            return answer

        flat: List[Dict[str, Any]] = []
        for group in sources.values():
            flat.extend(group)

        if not flat:
            return answer

        lines = [answer.strip(), "", "**Fuentes utilizadas**:"]
        for chunk in flat[:10]:
            doc_id = chunk.get('document_id', '')
            title = chunk.get('document_title', '')
            label = chunk.get('chunk_label', '')
            lines.append(f"- [ID: {doc_id}] {title} - {label}")

        return "\n".join(lines)

    def _format_sources(
        self,
        sources: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Format sources for API response.
        Maps internal fields to frontend-expected fields:
        - id: document_id
        - title: document_title
        - url: document_url
        - source_type: source_naturaleza
        - relevance_score: similarity/rrf_score
        - excerpt: chunk_text
        """
        formatted = []

        for naturaleza, chunks in sources.items():
            for chunk in chunks:
                formatted.append({
                    # Frontend-expected fields
                    'id': chunk.get('document_id', ''),
                    'title': chunk.get('document_title', ''),
                    'url': chunk.get('document_url', ''),
                    'source_type': chunk.get('source_naturaleza', ''),
                    'relevance_score': chunk.get('similarity', chunk.get('rrf_score', 0)),
                    'excerpt': chunk.get('chunk_text', '')[:300],  # Limit excerpt length

                    # Additional metadata (kept for backward compatibility)
                    'label': chunk.get('chunk_label', chunk.get('chunk_type', 'Sin etiqueta')),
                    'source_title': chunk.get('source_title', ''),
                    'source_priority': chunk.get('source_priority', ''),
                    'chunk_type': chunk.get('chunk_type', ''),
                })

        return formatted

    def _normalize_text(self, text: str) -> str:
        return self.intent_classifier._normalize_text(text) if text else ""

    def _source_matches_tokens(self, source: Dict[str, Any], tokens: List[str]) -> bool:
        haystack = " ".join([
            source.get('document_title', ''),
            source.get('source_title', ''),
            source.get('chunk_text', ''),
            source.get('chunk_label', ''),
        ]).lower()
        haystack = self._normalize_text(haystack)
        return any(tok in haystack for tok in tokens)

    def _filter_sources_by_area(
        self,
        area_principal: Optional[str],
        sources: Dict[str, List[Dict[str, Any]]],
        query: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Keep sources that match area-required terms or law-family hints, but fall back to original if filtering removes everything.
        """
        if not area_principal or area_principal not in self._area_required_terms:
            return sources

        required_terms = [self._normalize_text(t) for t in self._area_required_terms[area_principal]]
        law_hints = [self._normalize_text(t) for t in self._area_law_hints.get(area_principal, [])]
        area_tokens = [self._normalize_text(t) for t in self._area_tokens.get(area_principal, [])]
        query_tokens = [self._normalize_text(t) for t in self.intent_classifier.extract_keywords(query)]

        labor_core_terms = []
        labor_strict_terms = []
        artist_terms = []
        labor_doc_allowlist = set()
        if area_principal == "Laboral":
            labor_core_terms = [
                "seguridad social",
                "reta",
                "laboral",
                "autonomo",
                "autonomo",
                "contrato",
                "cotiz",
                "trabajo",
                "trabajador",
                "empleo",
            ]
            labor_strict_terms = [
                "relacion laboral",
                "contrato de trabajo",
                "estatuto",
                "seguridad social",
                "trabajador",
                "trabajo",
                "empleo",
                "cotizacion",
            ]
            artist_terms = ["artista", "artistas", "artistico", "artistica", "artisticos", "artisticas"]
            labor_doc_allowlist = {
                "BOE-A-1985-17303",
                "BOE-A-2022-4583",
                "BOE-A-2015-11430",
            }
            labor_core_terms = [self._normalize_text(t) for t in labor_core_terms]
            labor_strict_terms = [self._normalize_text(t) for t in labor_strict_terms]
            artist_terms = [self._normalize_text(t) for t in artist_terms]

        def keep(src: Dict[str, Any]) -> bool:
            # Laboral guard: require labor signal (avoid PI bleed-through on "artista").
            if labor_core_terms and artist_terms:
                doc_id = src.get("document_id")
                if doc_id in labor_doc_allowlist:
                    return True
                has_artist = self._source_matches_tokens(src, artist_terms)
                has_labor_core = self._source_matches_tokens(src, labor_core_terms)
                has_labor_strict = self._source_matches_tokens(src, labor_strict_terms)
                if has_artist and not (has_labor_core and has_labor_strict):
                    return False
                if not has_labor_strict and not has_labor_core:
                    return False
            # Priority: required terms > law-family hints > area tokens > query tokens
            if self._source_matches_tokens(src, required_terms):
                return True
            if law_hints and self._source_matches_tokens(src, law_hints):
                return True
            if area_tokens and self._source_matches_tokens(src, area_tokens):
                return True
            return bool(query_tokens) and self._source_matches_tokens(src, query_tokens)

        filtered = {k: [s for s in v if keep(s)] for k, v in sources.items()}
        filtered_total = sum(len(v) for v in filtered.values())
        original_total = sum(len(v) for v in sources.values())

        # If filtering wipes everything, keep originals (abstain will decide)
        if filtered_total == 0:
            return sources

        # Preserve relative order, but only keep relevant items
        return filtered

    def _should_abstain(
        self,
        query: str,
        area_principal: Optional[str],
        sources: Dict[str, List[Dict[str, Any]]]
    ) -> bool:
        """
        Determine if we should abstain due to weak or off-topic evidence.

        Heuristics:
        - No sources at all.
        - No source matches area-specific tokens (if area known).
        - If area unknown: require at least some keyword overlap with query.
        """
        total_sources = sum(len(v) for v in sources.values())
        if total_sources == 0:
            return True

        # Build tokens to check
        tokens: List[str] = []
        strict_tokens: List[str] = []
        if area_principal and area_principal in self._area_tokens:
            tokens.extend([self._normalize_text(t) for t in self._area_tokens[area_principal]])
            strict_tokens.extend([self._normalize_text(t) for t in self._area_required_terms.get(area_principal, [])])
            strict_tokens.extend([self._normalize_text(t) for t in self._area_law_hints.get(area_principal, [])])
        else:
            # fallback: use extracted keywords from query
            tokens.extend([self._normalize_text(t) for t in self.intent_classifier.extract_keywords(query)])

        if not tokens:
            return False  # nothing to match against

        def count_matches(token_list: List[str]) -> int:
            count = 0
            for group in sources.values():
                for src in group:
                    if self._source_matches_tokens(src, token_list):
                        count += 1
            return count

        # Strict: require minimum matches on law/required tokens when area is known
        if strict_tokens:
            strict_matches = count_matches(strict_tokens)
            if strict_matches < self._min_strict_matches:
                return True
            # Even if strict matches exist, also enforce a minimum on broader tokens

        # If the area is known and we have zero normativa/doctrina, abstain (likely off-topic)
        if area_principal:
            priority_sources = len(sources.get('normativa', [])) + len(sources.get('doctrina', []))
            if priority_sources < 1:
                return True
            # For Fiscal/IVA queries, require IVA/IRPF tokens in sources; otherwise abstain
            norm_query = self._normalize_text(query)
            if "iva" in norm_query:
                iva_tokens = ["iva", "impuesto sobre el valor añadido", "tipo impositivo"]
                if not any(self._source_matches_tokens(src, [self._normalize_text(t) for t in iva_tokens]) for grp in sources.values() for src in grp):
                    return True
        token_matches = count_matches(tokens)
        return token_matches < self._min_token_matches

    def _build_abstain_answer(self, query: str) -> str:
        return f"""A) ? Respuesta directa
Con las fuentes disponibles no puedo afirmar una regla concreta sobre: "{query}".

B) ?? Fundamento en fuentes
No hay evidencia suficiente en las fuentes recuperadas para sostener una respuesta precisa.

C) ?? C?mo aplicarlo / casos t?picos
Si aportas m?s contexto, puedo buscar la norma aplicable y explicarla con precisi?n.

D) ? Si falta evidencia: qu? falta exactamente + 1?3 preguntas concretas
1) ?En qu? pa?s o administraci?n se aplica tu caso (Espa?a/UE/CCAA)?
2) ?Cu?l es el tipo de actividad o relaci?n jur?dica espec?fica (p. ej., contrato, subvenci?n, IVA, PI)?
3) ?Qu? fechas o periodo concreto te interesa?
"""

    def _generate_fallback_answer(
        self,
        query: str,
        sources: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        Generate a fallback answer if LLM fails.
        """
        total_sources = sum(len(chunks) for chunks in sources.values())

        if total_sources == 0:
            return f"""A) ? Respuesta directa
Con las fuentes disponibles no puedo afirmar una regla concreta sobre: "{query}".

B) ?? Fundamento en fuentes
No se encontraron fuentes relevantes en el corpus para esta pregunta.

C) ?? C?mo aplicarlo / casos t?picos
Si me das m?s contexto, puedo buscar normativa aplicable y explicarla con citas.

D) ? Si falta evidencia: qu? falta exactamente + 1?3 preguntas concretas
1) ?Qu? norma o instituci?n espec?fica te interesa (p. ej., Ley 39/2015, BOE-A-...)?
2) ?Cu?l es el ?mbito y fecha relevante (Espa?a/UE/CCAA, a?o)?
3) ?Qu? situaci?n concreta necesitas resolver?
"""

        # If we have sources but LLM failed, provide a minimal grounded response
        source_list = []
        for naturaleza, chunks in sources.items():
            for chunk in chunks[:3]:  # Limit to top 3 per category
                doc_title = chunk.get('document_title', '')
                chunk_label = chunk.get('chunk_label', '')
                doc_id = chunk.get('document_id', '')
                source_list.append(f"- {doc_title} ({doc_id}) - {chunk_label}")

        return f"""A) ? Respuesta directa
He encontrado fuentes relevantes para tu pregunta, pero ocurri? un error al generar la respuesta completa.

B) ?? Fundamento en fuentes
Fuentes encontradas:
{chr(10).join(source_list)}

C) ?? C?mo aplicarlo / casos t?picos
Si indicas el aspecto exacto que necesitas (obligaciones, plazos, requisitos), puedo buscar el fragmento concreto.

D) ? Si falta evidencia: qu? falta exactamente + 1?3 preguntas concretas
1) ?Qu? punto espec?fico quieres aclarar?
2) ?Cu?l es tu contexto (actividad, relaci?n jur?dica, administraci?n)?
"""

