from __future__ import annotations

import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import spacy
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from langdetect import detect
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOG = logging.getLogger("nlp-api")

SENTENCE_MODEL = os.getenv(
    "SENTENCE_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
MODEL_PATH = Path(os.getenv("APP_MODEL_PATH", "/app/model/classifier.joblib"))
MODEL_METADATA_PATH = Path(os.getenv("APP_MODEL_METADATA_PATH", "/app/model/metadata.json"))

REQUESTS = Counter(
    "nlp_http_requests_total",
    "HTTP requests processed by the NLP API",
    ["method", "path", "status"],
)
REQUEST_DURATION = Histogram(
    "nlp_http_request_duration_seconds",
    "HTTP request latency for the NLP API",
    ["method", "path"],
)
ANALYSES = Counter(
    "nlp_analyses_total",
    "Complaint analyses completed",
    ["language", "sentiment"],
)
MODEL_READY = Gauge("nlp_model_ready", "1 when the NLP model is loaded")
MODEL_LOAD_SECONDS = Gauge("nlp_model_load_seconds", "Seconds required to load the NLP pipeline")

SPANISH_POSITIVE = {
    "bien", "bueno", "correcto", "excelente", "gracias", "resuelto", "solucionado", "satisfecho"
}
SPANISH_NEGATIVE = {
    "mal", "malo", "fraude", "error", "cobro", "incumplimiento", "problema", "queja",
    "reclamo", "negado", "rechazado", "injusto", "demora", "deuda", "acosado", "afectado"
}


def classify_spanish_sentiment(text: str) -> str:
    tokens = re.findall(r"[a-záéíóúñü]+", text.lower())
    score = sum(token in SPANISH_POSITIVE for token in tokens) - sum(
        token in SPANISH_NEGATIVE for token in tokens
    )
    if score <= -2:
        return "Crítico/Muy Negativo"
    if score < 0:
        return "Negativo"
    return "Neutral/Positivo"


class MultilingualLinguisticEngine:
    def __init__(self) -> None:
        LOG.info("Loading spaCy language models")
        self.nlp_en = spacy.load("en_core_web_sm")
        self.nlp_es = spacy.load("es_core_news_md")
        self._add_colombian_financial_rules(self.nlp_en)
        self._add_colombian_financial_rules(self.nlp_es)

    @staticmethod
    def _add_colombian_financial_rules(nlp: Any) -> None:
        ruler = nlp.add_pipe("entity_ruler", before="ner")
        banks = [
            "Bancolombia", "Davivienda", "Banco de Bogotá", "Banco de Occidente",
            "Banco Popular", "Banco AV Villas", "Banco Caja Social", "BBVA Colombia",
            "Scotiabank Colpatria", "Banco GNB Sudameris", "Banco Itaú", "Banco Agrario",
            "Banco Pichincha", "Banco Falabella", "Banco Finandina", "Banco Santander",
            "Banco Serfinanza", "Lulo Bank", "Nubank", "Nu Colombia", "RappiPay",
            "Nequi", "Daviplata",
        ]
        patterns: list[dict[str, Any]] = [
            {"label": "ORG", "pattern": [{"LOWER": word.lower()} for word in bank.split()]}
            for bank in banks
        ]
        patterns.extend(
            [
                {"label": "LAW", "pattern": "FCRA"},
                {"label": "LAW", "pattern": [{"LOWER": "section"}, {"LIKE_NUM": True}]},
            ]
        )
        patterns.extend(
            {"label": "LAW", "pattern": [{"LOWER": "ley"}, {"TEXT": law}]}
            for law in ["1581", "1266", "1564", "1116", "2445"]
        )
        ruler.add_patterns(patterns)

    def extract_svo_and_entities(self, text: str, language: str) -> tuple[list[dict[str, str]], dict[str, list[str]]]:
        nlp = self.nlp_en if language == "en" else self.nlp_es
        document = nlp(text)
        svo: list[dict[str, str]] = []
        entities: dict[str, list[str]] = {"ORG": [], "MONEY": [], "LAW": []}

        for token in document:
            if token.dep_ == "ROOT":
                subjects = [word.text for word in token.lefts if word.dep_ in ("nsubj", "nsubjpass")]
                objects = [
                    word.text for word in token.rights if word.dep_ in ("dobj", "obj", "pobj", "ccomp")
                ]
                svo.append(
                    {
                        "Sujeto": subjects[0] if subjects else "Desconocido",
                        "Accion": token.lemma_,
                        "Objeto": objects[0] if objects else "Desconocido",
                    }
                )

        for entity in document.ents:
            if "XXXX" not in entity.text and entity.label_ in entities:
                entities[entity.label_].append(entity.text)

        return svo, {key: sorted(set(values)) for key, values in entities.items()}


class SemanticEngine:
    def __init__(self) -> None:
        LOG.info("Loading multilingual sentence-transformer")
        self.sbert = SentenceTransformer(SENTENCE_MODEL, device="cpu")
        self.vader = SentimentIntensityAnalyzer()

    def vectorize(self, texts: list[str]) -> np.ndarray:
        return self.sbert.encode(
            texts,
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def get_sentiment(self, text: str, language: str) -> str:
        if language == "es":
            return classify_spanish_sentiment(text)

        compound = self.vader.polarity_scores(text)["compound"]
        if compound <= -0.2:
            return "Crítico/Muy Negativo"
        if compound < 0:
            return "Negativo"
        return "Neutral/Positivo"


class ComplaintClassifierPipeline:
    def __init__(self) -> None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Classifier artifact not found: {MODEL_PATH}")

        self.linguistic = MultilingualLinguisticEngine()
        self.semantic = SemanticEngine()
        self.classifier = joblib.load(MODEL_PATH)
        self.metadata: dict[str, Any] = {}
        if MODEL_METADATA_PATH.exists():
            self.metadata = json.loads(MODEL_METADATA_PATH.read_text(encoding="utf-8"))

    def analyze(self, text: str) -> dict[str, Any]:
        try:
            language = detect(text)
            if language not in {"en", "es"}:
                language = "en"
        except Exception:
            language = "en"

        clean_text = text.replace("XXXX", "[MASK]")
        svo, entities = self.linguistic.extract_svo_and_entities(clean_text, language)
        vector = self.semantic.vectorize([clean_text])
        sentiment = self.semantic.get_sentiment(clean_text, language)
        prediction = str(self.classifier.predict(vector)[0])
        confidence = float(np.max(self.classifier.predict_proba(vector)))
        ANALYSES.labels(language=language, sentiment=sentiment).inc()

        return {
            "idioma_detectado": language,
            "texto_ingresado": text,
            "analisis_sentimiento": sentiment,
            "prediccion_issue": prediction,
            "nivel_confianza_porcentaje": round(confidence * 100, 2),
            "estructura_gramatical_svo": svo,
            "entidades_detectadas": entities,
        }


pipeline: ComplaintClassifierPipeline | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global pipeline
    started = time.perf_counter()
    MODEL_READY.set(0)
    pipeline = ComplaintClassifierPipeline()
    MODEL_LOAD_SECONDS.set(time.perf_counter() - started)
    MODEL_READY.set(1)
    LOG.info("NLP pipeline ready")
    try:
        yield
    finally:
        MODEL_READY.set(0)
        pipeline = None


app = FastAPI(
    title="API Motor de Quejas CFPB Multilingüe",
    version="3.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials="*" not in allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        REQUESTS.labels(request.method, path, str(status_code)).inc()
        REQUEST_DURATION.labels(request.method, path).observe(time.perf_counter() - started)


class Complaint(BaseModel):
    texto: str = Field(min_length=5, max_length=5000)


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="model not ready")
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/analizar", tags=["analysis"])
def analyze_complaint(complaint: Complaint) -> dict[str, Any]:
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="model not ready")
    try:
        return pipeline.analyze(complaint.texto)
    except Exception as exc:
        LOG.exception("Complaint analysis failed")
        raise HTTPException(status_code=500, detail="analysis failed") from exc
