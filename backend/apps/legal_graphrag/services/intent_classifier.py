"""
Intent Classifier for Legal GraphRAG
Classifies user queries into legal areas using keyword matching.
"""

from typing import Optional, List, Dict
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


class IntentClassifier:
    """
    Simple keyword-based intent classifier for legal queries.

    Classifies user queries into legal areas (Fiscal, Laboral, Propiedad Intelectual, etc.)
    based on keyword matching.

    Post-MVP: Replace with ML classifier (fine-tuned BERT/transformer model).
    """

    AREA_KEYWORDS = {
        "Fiscal": [
            "iva",
            "irpf",
            "impuesto",
            "tribut",
            "fiscal",
            "hacienda",
            "deducci",
            "deducir",
            "retencion",
            "retenciones",
            "retener",
            "declaracion",
            "aeat",
            "dgt",
            "mecenazgo",
            "exencion",
            "base imponible",
            "tipo impositivo",
            "renta",
            "autoliquidacion",
            "modulos",
            "estimacion directa",
            "estimacion objetiva",
            "liquidacion",
            "factura",
            "facturacion",
            "gasto deducible",
        ],
        "Laboral": [
            "contrato",
            "contratar",
            "contratacion",
            "laboral",
            "empleo",
            "empleado",
            "trabajador",
            "salario",
            "salarial",
            "autonomo",
            "seguridad social",
            "cotiza",
            "cotizacion",
            "despido",
            "convenio",
            "nomina",
            "alta",
            "baja",
            "afiliar",
            "afiliacion",
            "reta",
            "freelance",
            "cuenta propia",
            "cuenta ajena",
            "jornada",
            "vacaciones",
            "finiquito",
            "paro",
            "desempleo",
            "cuota",
        ],
        "Propiedad Intelectual": [
            "derechos de autor",
            "copyright",
            "propiedad intelectual",
            "sgae",
            "cedro",
            "vegap",
            "registro",
            "registrar",
            "licencia",
            "licenciar",
            "obra",
            "plagio",
            "copia",
            "copiar",
            "royalt",
            "royalty",
            "cesion",
            "explotacion",
            "reproduccion",
            "distribucion",
            "comunicacion publica",
            "transformacion",
            "dominio publico",
            "foto",
            "imagen",
            "internet",
            "cancion",
            "musica",
            "sample",
            "cover",
            "denuncia",
        ],
        "Contabilidad": [
            "contab",
            "pgc",
            "libro",
            "libro registro",
            "asiento",
            "balance",
            "cuenta",
            "amortiza",
            "amortizacion",
            "provision",
            "patrimonio",
            "debe",
            "haber",
            "resultado",
            "perdidas",
            "ganancias",
            "activo",
            "pasivo",
            "existencias",
            "inmovilizado",
            "factura",
            "facturacion",
        ],
        "Subvenciones": [
            "subvencion",
            "subvenciones",
            "ayuda",
            "beca",
            "grant",
            "convocatoria",
            "solicitud",
            "elegib",
            "eligibilidad",
            "ministerio",
            "cultura",
            "financiacion",
            "fondos",
            "dotacion",
            "concurrencia",
            "beneficiario",
            "justificacion",
            "pago",
            "subsidio",
            "subsidios",
            "linea de ayudas",
        ],
        "Societario": [
            "sociedad",
            "sociedad anonima",
            "sociedad limitada",
            "mercantil",
            "constitucion",
            "estatutos",
            "junta",
            "accionista",
            "socio",
            "participacion",
            "capital social",
            "escritura",
            "registro mercantil",
            "administrador",
            "disolucion",
            "empresa",
            "compania",
        ],
        "Administrativo": [
            "licencia",
            "licencia de actividad",
            "licencia de apertura",
            "permiso",
            "autorizacion",
            "certificado",
            "procedimiento administrativo",
            "recurso",
            "silencio administrativo",
            "notificacion",
            "plazo",
            "subsanacion",
            "alegacion",
            "resolucion",
            "denegacion",
            "estimacion",
            "tramite",
            "ayuntamiento",
            "grabacion",
            "estudio de grabacion",
            "apertura",
        ],
    }

    STOPWORDS = {
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "de",
        "del",
        "en",
        "para",
        "por",
        "con",
        "sin",
        "sobre",
        "es",
        "son",
        "ser",
        "estar",
        "pueden",
        "puede",
        "debo",
        "debe",
        "deben",
        "que",
        "cual",
        "cuales",
        "donde",
        "cuando",
        "cuanto",
        "cuantos",
        "si",
        "no",
        "ya",
        "aun",
        "tambien",
        "pero",
        "a",
        "o",
        "y",
        "e",
        "u",
        "ni",
        "mi",
        "mis",
        "tu",
        "tus",
        "su",
        "sus",
        "me",
        "te",
        "se",
        "le",
        "lo",
        "les",
        "hay",
        "he",
        "has",
        "ha",
        "han",
        "hemos",
    }

    def __init__(self) -> None:
        # Normalize keywords once to make matching accent-insensitive.
        self.normalized_area_keywords: Dict[str, List[str]] = {
            area: [
                norm_kw
                for kw in keywords
                for norm_kw in [self._normalize_text(kw)]
                if norm_kw
            ]
            for area, keywords in self.AREA_KEYWORDS.items()
        }

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Lowercase and strip accents/non-word characters for robust matching.
        """
        normalized = unicodedata.normalize("NFKD", text.lower())
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        normalized = re.sub(r"[^a-z0-9\s]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _score_query(self, query: str) -> Dict[str, int]:
        """
        Compute keyword match scores for each area on the normalized query.
        """
        normalized_query = self._normalize_text(query)
        if not normalized_query:
            return {}

        scores: Dict[str, int] = {}
        for area, keywords in self.normalized_area_keywords.items():
            score = sum(1 for kw in keywords if kw in normalized_query)
            if score:
                scores[area] = score
        return scores

    def classify_area(self, query: str) -> Optional[str]:
        """
        Classify query into a legal area based on keyword matching.

        Args:
            query: User query text

        Returns:
            Area name (e.g., 'Fiscal', 'Laboral') or None if no clear match.

        Example:
            >>> classifier = IntentClassifier()
            >>> classifier.classify_area("¿Puedo deducir gastos de mi home studio?")
            'Fiscal'
        """
        scores = self._score_query(query)
        if not scores:
            logger.info(f"No area classification for query: {query[:50]}")
            return None

        best_area, best_score = max(scores.items(), key=lambda item: item[1])
        logger.info(f"Classified query as '{best_area}' (score: {best_score})")
        return best_area

    def extract_keywords(self, query: str) -> List[str]:
        """
        Extract important keywords from query by removing stopwords.

        Args:
            query: User query text

        Returns:
            List of extracted keywords (lowercased, >3 chars, no stopwords).

        Example:
            >>> classifier = IntentClassifier()
            >>> classifier.extract_keywords("¿Cómo puedo deducir los gastos?")
            ['como', 'puedo', 'deducir', 'gastos']
        """
        normalized = self._normalize_text(query)
        if not normalized:
            return []

        keywords = [
            word
            for word in normalized.split()
            if word not in self.STOPWORDS and len(word) > 2
        ]

        logger.debug(f"Extracted keywords: {keywords}")
        return keywords

    def get_all_areas(self) -> List[str]:
        """
        Get list of all available legal areas.

        Returns:
            List of area names.
        """
        return list(self.AREA_KEYWORDS.keys())

    def get_keywords_for_area(self, area: str) -> List[str]:
        """
        Get keywords associated with a specific area.

        Args:
            area: Legal area name

        Returns:
            List of keywords for that area, or empty list if area not found.
        """
        return self.AREA_KEYWORDS.get(area, [])

    def classify_with_confidence(self, query: str) -> dict:
        """
        Classify query and return confidence scores for all areas.

        Args:
            query: User query text

        Returns:
            Dictionary with:
            - 'area': Best matching area or None
            - 'confidence': Normalized score of best area
            - 'scores': Dict of all area scores

        Example:
            >>> classifier = IntentClassifier()
            >>> classifier.classify_with_confidence("¿Puedo deducir gastos?")
            {'area': 'Fiscal', 'confidence': 0.75, 'scores': {'Fiscal': 3, 'Laboral': 1}}
        """
        scores = self._score_query(query)
        if not scores:
            return {"area": None, "confidence": 0.0, "scores": {}}

        total_score = sum(scores.values())
        best_area, best_score = max(scores.items(), key=lambda item: item[1])
        confidence = best_score / total_score if total_score else 0.0

        return {"area": best_area, "confidence": confidence, "scores": scores}
