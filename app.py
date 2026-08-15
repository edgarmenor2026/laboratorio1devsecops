from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import spacy
from sentence_transformers import SentenceTransformer
from sklearn.neural_network import MLPClassifier
from textblob import TextBlob
import numpy as np
import logging
import warnings
from fastapi.middleware.cors import CORSMiddleware
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from langdetect import detect  # Nueva dependencia
from googletrans import Translator # Para apoyo en sentimiento multilingüe

warnings.filterwarnings('ignore')
nltk.download('vader_lexicon', quiet=True)

# 1. DEFINICIÓN DE MOTORES DE IA (Arquitectura Multilingüe)
class MultilingualLinguisticEngine:
    def __init__(self):
        # Cargamos ambos modelos para soporte bilingüe
        print("Cargando modelos lingüísticos (EN/ES)...")
        self.nlp_en = spacy.load("en_core_web_sm")
        self.nlp_es = spacy.load("es_core_news_md")
        
        # Inyectamos reglas de entidades financieras de Colombia en ambos modelos
        self._add_colombian_financial_rules(self.nlp_en)
        self._add_colombian_financial_rules(self.nlp_es)

    def _add_colombian_financial_rules(self, nlp):
        ruler = nlp.add_pipe("entity_ruler", before="ner")
        
        # Lista exhaustiva de entidades financieras de Colombia
        bancos_colombia = [
            "Bancolombia", "Davivienda", "Banco de Bogotá", "Banco de Occidente", 
            "Banco Popular", "Banco AV Villas", "Banco Caja Social", "BBVA Colombia", 
            "Scotiabank Colpatria", "Banco GNB Sudameris", "Banco Itaú", "Banco Agrario", 
            "Banco Pichincha", "Banco Falabella", "Banco Finandina", "Banco Santander", 
            "Banco Serfinanza", "Lulo Bank", "Nubank", "Nu Colombia", "RappiPay", "Nequi", "Daviplata"
        ]
        
        patterns = []
        # Reglas para bancos
        for banco in bancos_colombia:
            patterns.append({"label": "ORG", "pattern": [{"LOWER": word.lower()} for word in banco.split()]})
        
        # Reglas para leyes (FCRA y Ley 1581 de protección de datos)
        patterns.extend([
            {"label": "LAW", "pattern": "FCRA"},
            {"label": "LAW", "pattern": [{"LOWER": "section"}, {"LIKE_NUM": True}]},
            {"label": "LAW", "pattern": [{"LOWER": "ley"}, {"TEXT": "1581"}]},
            {"label": "LAW", "pattern": [{"LOWER": "ley"}, {"TEXT": "1266"}]},
            {"label": "LAW", "pattern": [{"LOWER": "ley"}, {"TEXT": "1564"}]},                
            {"label": "LAW", "pattern": [{"LOWER": "ley"}, {"TEXT": "1116"}]},
            {"label": "LAW", "pattern": [{"LOWER": "ley"}, {"TEXT": "2445"}]}
                ])
        
        ruler.add_patterns(patterns)

    def extract_svo_and_entities(self, text, lang):
        # Seleccionamos el motor según el idioma detectado
        nlp = self.nlp_en if lang == 'en' else self.nlp_es
        doc = nlp(text)
        
        svo_list = []
        entidades = {"ORG": [], "MONEY": [], "LAW": []}

        # Extracción SVO
        for token in doc:
            if token.dep_ == "ROOT":
                sujeto = [w.text for w in token.lefts if w.dep_ in ("nsubj", "nsubjpass")]
                objeto = [w.text for w in token.rights if w.dep_ in ("dobj", "pobj", "ccomp")]
                svo_list.append({
                    "Sujeto": sujeto[0] if sujeto else "Desconocido",
                    "Accion": token.lemma_,
                    "Objeto": objeto[0] if objeto else "Desconocido"
                })

        # Extracción NER
        for ent in doc.ents:
            if "XXXX" not in ent.text and ent.label_ in entidades:
                entidades[ent.label_].append(ent.text)

        return svo_list, {k: list(set(v)) for k, v in entidades.items()}

class SemanticEngine:
    def __init__(self):
        # CAMBIO CLAVE: Modelo Multilingüe de SBERT
        print("Cargando Sentence-Transformer Multilingüe...")
        self.sbert = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.vader = SentimentIntensityAnalyzer()
        self.translator = Translator()

    def vectorize(self, texts):
        return self.sbert.encode(texts, show_progress_bar=False)

    def get_sentiment(self, text, lang):
        # Si es español, traducimos brevemente para una mejor precisión con VADER
        text_to_analyze = text
        if lang == 'es':
            try:
                translated = self.translator.translate(text, dest='en')
                text_to_analyze = translated.text
            except:
                pass 

        scores = self.vader.polarity_scores(text_to_analyze)
        compound = scores['compound']
        if compound <= -0.2: return "Crítico/Muy Negativo"
        elif compound < 0: return "Negativo"
        else: return "Neutral/Positivo"

class ComplaintClassifierPipeline:
    def __init__(self, data_path):
        self.linguistic = MultilingualLinguisticEngine()
        self.semantic = SemanticEngine()
        self.classifier = MLPClassifier(hidden_layer_sizes=(128,), activation='relu', max_iter=500, random_state=42)
        
        # Entrenamiento (Se asume carga de modelo pre-entrenado en producción)
        df = pd.read_csv(data_path).dropna(subset=['Consumer complaint narrative', 'Issue']).head(20000)
        df['clean_text'] = df['Consumer complaint narrative'].str.replace("XXXX", "[MASK]")
        X = self.semantic.vectorize(df['clean_text'].tolist())
        y = df['Issue'].tolist()
        self.classifier.fit(X, y)

    def analyze(self, text):
        # 1. Detectar idioma
        try:
            lang = detect(text)
            if lang not in ['en', 'es']: lang = 'en'
        except:
            lang = 'en'
            
        clean_text = text.replace("XXXX", "[MASK]")
        
        # 2. Pipeline
        svos, entidades = self.linguistic.extract_svo_and_entities(clean_text, lang)
        vector = self.semantic.vectorize([clean_text])
        sentimiento = self.semantic.get_sentiment(clean_text, lang)
        
        # 3. Predicción
        prediccion = self.classifier.predict(vector)[0]
        probabilidad = np.max(self.classifier.predict_proba(vector))

        return {
            "idioma_detectado": lang,
            "texto_ingresado": text,
            "analisis_sentimiento": sentimiento,
            "prediccion_issue": prediccion,
            "nivel_confianza_porcentaje": round(float(probabilidad) * 100, 2),
            "estructura_gramatical_svo": svos,
            "entidades_detectadas": entidades
        }

# 2. CONFIGURACIÓN DE LA API
app = FastAPI(title="API Motor de Quejas CFPB Multilingüe", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = ComplaintClassifierPipeline("muestra_nlp_limpia.csv")

class Reclamo(BaseModel):
    texto: str

@app.post("/api/analizar")
def procesar_queja(reclamo: Reclamo):
    return pipeline.analyze(reclamo.texto)
    