from apps.legal_graphrag.services.v1_1.tax_rate_resolver import (
    TaxRateResolver,
    sanitize_answer_percentages,
)


def test_iva_teatro_resolves_10():
    resolver = TaxRateResolver()
    result = resolver.resolve_iva({"topic": "unknown", "keywords": ["teatro", "entrada"]})
    assert result["status"] == "ok"
    assert result["rate_percent"] == 10


def test_iva_accented_keyword_resolves_10():
    resolver = TaxRateResolver()
    result = resolver.resolve_iva({"topic": "unknown", "keywords": ["t\u00e9cnico"]})
    assert result["status"] == "ok"
    assert result["rate_percent"] == 10


def test_iva_synonym_restauracion_resolves_10():
    resolver = TaxRateResolver()
    result = resolver.resolve_iva({"topic": "unknown", "keywords": ["restauracion"]})
    assert result["status"] == "ok"
    assert result["rate_percent"] == 10


def test_iva_hosteleria_restaurante_resolves_10():
    resolver = TaxRateResolver()
    result = resolver.resolve_iva({
        "topic": "unknown",
        "keywords": ["restaurante", "comidas", "bebidas"],
    })
    assert result["status"] == "ok"
    assert result["rate_percent"] == 10


def test_iva_general_resolves_21():
    resolver = TaxRateResolver()
    result = resolver.resolve_iva({"topic": "unknown", "keywords": ["servicio", "general"]})
    assert result["status"] == "ok"
    assert result["rate_percent"] == 21


def test_irpf_profesional_new_activity_resolves_7():
    resolver = TaxRateResolver()
    result = resolver.resolve_irpf({
        "income_type": "actividad_profesional",
        "new_activity": True,
        "net_turnover_bucket": None,
    })
    assert result["status"] == "ok"
    assert result["rate_percent"] == 7


def test_irpf_admin_missing_turnover_needs_clarification():
    resolver = TaxRateResolver()
    result = resolver.resolve_irpf({
        "income_type": "consejero_administrador",
        "new_activity": None,
        "net_turnover_bucket": None,
    })
    assert result["status"] == "needs_clarification"
    assert "100.000" in result.get("clarifying_question", "")


def test_resolver_is_deterministic():
    resolver = TaxRateResolver()
    intent = {"topic": "unknown", "keywords": ["teatro", "entrada"]}
    first = resolver.resolve_iva(intent)
    second = resolver.resolve_iva(intent)
    assert first == second


def test_validator_rejects_unresolved_percentage():
    result = sanitize_answer_percentages(
        "El tipo aplicable es 12% segun la norma.",
        allowed_percentages=[21],
    )
    assert result["changed"] is True
    assert "12%" not in result["text"]


def test_validator_allows_non_tax_allowlist():
    result = sanitize_answer_percentages(
        "La bonificacion general es 30% segun el reglamento.",
        allowed_percentages=[21],
        non_tax_allowlist=[30],
    )
    assert result["changed"] is False
    assert "30%" in result["text"]
