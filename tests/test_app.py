from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response

import app as app_module


class FakeWord:
    def __init__(self, text: str, dependency: str):
        self.text = text
        self.dep_ = dependency


class FakeRoot(FakeWord):
    def __init__(self):
        super().__init__("cobrar", "ROOT")
        self.lemma_ = "cobrar"
        self.lefts = [FakeWord("banco", "nsubj")]
        self.rights = [FakeWord("deuda", "obj")]


class FakeDocument:
    def __init__(self):
        self.tokens = [FakeRoot()]
        self.ents = [
            SimpleNamespace(text="Bancolombia", label_="ORG"),
            SimpleNamespace(text="$100", label_="MONEY"),
            SimpleNamespace(text="XXXX", label_="ORG"),
        ]

    def __iter__(self):
        return iter(self.tokens)


def test_spanish_sentiment_branches() -> None:
    assert app_module.classify_spanish_sentiment("fraude deuda problema") == "Crítico/Muy Negativo"
    assert app_module.classify_spanish_sentiment("un cobro") == "Negativo"
    assert app_module.classify_spanish_sentiment("gracias, quedó resuelto") == "Neutral/Positivo"


def test_financial_entity_rules_are_registered() -> None:
    class FakeRuler:
        def __init__(self):
            self.patterns = []

        def add_patterns(self, patterns):
            self.patterns.extend(patterns)

    class FakeNlp:
        def __init__(self):
            self.ruler = FakeRuler()

        def add_pipe(self, name, before):
            assert name == "entity_ruler"
            assert before == "ner"
            return self.ruler

    nlp = FakeNlp()
    app_module.MultilingualLinguisticEngine._add_colombian_financial_rules(nlp)
    labels = {pattern["label"] for pattern in nlp.ruler.patterns}
    assert {"ORG", "LAW"} <= labels
    assert len(nlp.ruler.patterns) >= 30


def test_extract_svo_and_entities() -> None:
    engine = app_module.MultilingualLinguisticEngine.__new__(app_module.MultilingualLinguisticEngine)
    engine.nlp_en = lambda _text: FakeDocument()
    engine.nlp_es = lambda _text: FakeDocument()

    svo, entities = engine.extract_svo_and_entities("texto", "es")

    assert svo == [{"Sujeto": "banco", "Accion": "cobrar", "Objeto": "deuda"}]
    assert entities == {"ORG": ["Bancolombia"], "MONEY": ["$100"], "LAW": []}


@pytest.mark.parametrize(
    ("compound", "expected"),
    [(-0.7, "Crítico/Muy Negativo"), (-0.1, "Negativo"), (0.1, "Neutral/Positivo")],
)
def test_english_sentiment_branches(compound: float, expected: str) -> None:
    engine = app_module.SemanticEngine.__new__(app_module.SemanticEngine)
    engine.vader = SimpleNamespace(polarity_scores=lambda _text: {"compound": compound})
    assert engine.get_sentiment("sample", "en") == expected


def test_semantic_engine_uses_spanish_classifier() -> None:
    engine = app_module.SemanticEngine.__new__(app_module.SemanticEngine)
    engine.vader = SimpleNamespace(polarity_scores=lambda _text: {"compound": 0.0})
    assert engine.get_sentiment("fraude deuda", "es") == "Crítico/Muy Negativo"


def test_pipeline_constructor_loads_artifacts(monkeypatch, tmp_path: Path) -> None:
    model_path = tmp_path / "classifier.joblib"
    metadata_path = tmp_path / "metadata.json"
    model_path.write_bytes(b"placeholder")
    metadata_path.write_text(json.dumps({"classes": ["A", "B"]}), encoding="utf-8")

    fake_classifier = object()
    monkeypatch.setattr(app_module, "MODEL_PATH", model_path)
    monkeypatch.setattr(app_module, "MODEL_METADATA_PATH", metadata_path)
    monkeypatch.setattr(app_module, "MultilingualLinguisticEngine", lambda: "linguistic")
    monkeypatch.setattr(app_module, "SemanticEngine", lambda: "semantic")
    monkeypatch.setattr(app_module.joblib, "load", lambda _path: fake_classifier)

    pipeline = app_module.ComplaintClassifierPipeline()
    assert pipeline.linguistic == "linguistic"
    assert pipeline.semantic == "semantic"
    assert pipeline.classifier is fake_classifier
    assert pipeline.metadata["classes"] == ["A", "B"]


def test_pipeline_constructor_rejects_missing_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app_module, "MODEL_PATH", tmp_path / "missing.joblib")
    with pytest.raises(FileNotFoundError):
        app_module.ComplaintClassifierPipeline()


def make_pipeline() -> app_module.ComplaintClassifierPipeline:
    pipeline = app_module.ComplaintClassifierPipeline.__new__(app_module.ComplaintClassifierPipeline)
    pipeline.linguistic = SimpleNamespace(
        extract_svo_and_entities=lambda _text, _language: ([{"Accion": "reportar"}], {"ORG": []})
    )
    pipeline.semantic = SimpleNamespace(
        vectorize=lambda _texts: np.array([[0.1, 0.2]]),
        get_sentiment=lambda _text, _language: "Negativo",
    )
    pipeline.classifier = SimpleNamespace(
        predict=lambda _vector: np.array(["Incorrect information"]),
        predict_proba=lambda _vector: np.array([[0.25, 0.75]]),
    )
    pipeline.metadata = {}
    return pipeline


def test_pipeline_analysis(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "detect", lambda _text: "es")
    result = make_pipeline().analyze("Bancolombia reportó una deuda XXXX")
    assert result["idioma_detectado"] == "es"
    assert result["prediccion_issue"] == "Incorrect information"
    assert result["nivel_confianza_porcentaje"] == 75.0


def test_pipeline_falls_back_to_english(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "detect", lambda _text: "fr")
    assert make_pipeline().analyze("sample")["idioma_detectado"] == "en"

    def fail(_text):
        raise RuntimeError("cannot detect")

    monkeypatch.setattr(app_module, "detect", fail)
    assert make_pipeline().analyze("sample")["idioma_detectado"] == "en"


def test_health_and_metrics_endpoints(monkeypatch) -> None:
    assert app_module.liveness() == {"status": "alive"}

    monkeypatch.setattr(app_module, "pipeline", None)
    with pytest.raises(HTTPException) as error:
        app_module.readiness()
    assert error.value.status_code == 503

    monkeypatch.setattr(app_module, "pipeline", object())
    assert app_module.readiness() == {"status": "ready"}

    response = app_module.metrics()
    assert response.status_code == 200
    assert b"nlp_model_ready" in response.body


def test_request_contract_and_analysis_endpoint(monkeypatch) -> None:
    with pytest.raises(ValidationError):
        app_module.Complaint(texto="bad")

    fake = SimpleNamespace(analyze=lambda text: {"texto": text})
    monkeypatch.setattr(app_module, "pipeline", fake)
    assert app_module.analyze_complaint(app_module.Complaint(texto="reclamo valido")) == {
        "texto": "reclamo valido"
    }

    monkeypatch.setattr(app_module, "pipeline", None)
    with pytest.raises(HTTPException) as unavailable:
        app_module.analyze_complaint(app_module.Complaint(texto="reclamo valido"))
    assert unavailable.value.status_code == 503

    fake = SimpleNamespace(analyze=lambda _text: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(app_module, "pipeline", fake)
    with pytest.raises(HTTPException) as failed:
        app_module.analyze_complaint(app_module.Complaint(texto="reclamo valido"))
    assert failed.value.status_code == 500


def test_lifespan_loads_and_releases_pipeline(monkeypatch) -> None:
    fake_pipeline = object()
    monkeypatch.setattr(app_module, "ComplaintClassifierPipeline", lambda: fake_pipeline)

    async def scenario() -> None:
        async with app_module.lifespan(app_module.app):
            assert app_module.pipeline is fake_pipeline
        assert app_module.pipeline is None

    asyncio.run(scenario())


def test_observability_middleware() -> None:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/health/live",
        "raw_path": b"/health/live",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }
    request = Request(scope)

    async def call_next(_request):
        return Response("ok", status_code=201)

    response = asyncio.run(app_module.observe_requests(request, call_next))
    assert response.status_code == 201
