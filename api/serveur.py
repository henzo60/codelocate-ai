"""API locale de CodeLocate AI (FastAPI).

Routes :
    GET  /sante      -> état du service (Ollama joignable, projet indexé)
    POST /indexer    -> indexe un projet à partir de son chemin
    POST /question   -> pose une question, reçoit la réponse et ses sources

Lancement : python -m api.serveur
Documentation interactive : http://127.0.0.1:8000/docs
"""
import time
import uuid
from pathlib import Path

import ollama
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import config
from chatbot.conversation import Conversation
from indexation.indexeur import indexer_projet, obtenir_collection
from outils import analyse
from recherche import mots_cles

HOTE = "127.0.0.1"  # uniquement sur ton PC : le service n'est pas visible depuis le réseau
PORT = 8000

app = FastAPI(
    title="CodeLocate AI",
    description="L'assistant de code 100 % local qui cite ses sources.",
    version="1.0",
)

conversations = {}  # une mémoire de conversation par session_id


class DemandeIndexation(BaseModel):
    dossier: str = Field(..., description="Chemin du projet Python à indexer",
                         examples=["C:/Users/USER/Projets/gestion_bibliotheque"])


class DemandeQuestion(BaseModel):
    question: str = Field(..., min_length=2, examples=["Que fait la fonction calculer_penalite ?"])
    session_id: str | None = Field(
        None, description="Identifiant de conversation, à renvoyer pour poser une question de suivi"
    )


def vider_caches():
    """Après une nouvelle indexation, oublie les index gardés en mémoire (BM25, découpage)."""
    mots_cles._cache.clear()
    analyse.morceaux_du_projet.__defaults__[0].clear()


@app.get("/sante")
def sante():
    """Vérifie qu'Ollama répond et indique quel projet est indexé."""
    try:
        modeles = [m.model for m in ollama.list().models]
        ollama_ok = True
    except Exception:
        modeles, ollama_ok = [], False
    collection = obtenir_collection()
    return {
        "ollama": ollama_ok,
        "modeles_disponibles": modeles,
        "projet_indexe": collection.metadata.get("projet") if collection else None,
        "morceaux": collection.count() if collection else 0,
    }


@app.post("/indexer")
def indexer(demande: DemandeIndexation):
    """Découpe le projet, crée les embeddings et remplace la base (peut prendre une minute)."""
    dossier = Path(demande.dossier).expanduser()
    if not dossier.is_dir():
        raise HTTPException(status_code=400, detail=f"Dossier introuvable : {dossier}")
    depart = time.perf_counter()
    try:
        collection = indexer_projet(dossier)
    except ValueError as erreur:
        raise HTTPException(status_code=400, detail=str(erreur))
    except Exception as erreur:
        raise HTTPException(status_code=503, detail=f"Indexation impossible (Ollama est-il lancé ?) : {erreur}")
    vider_caches()
    conversations.clear()
    return {
        "projet": str(dossier.resolve()),
        "morceaux": collection.count(),
        "duree": round(time.perf_counter() - depart, 1),
    }


@app.post("/question")
def question(demande: DemandeQuestion):
    """Répond en français en citant fichiers et lignes. Renvoie le session_id pour continuer la conversation."""
    if obtenir_collection() is None:
        raise HTTPException(status_code=400, detail="Aucun projet indexé : utilise d'abord /indexer.")
    session_id = demande.session_id or uuid.uuid4().hex[:8]
    conversation = conversations.setdefault(session_id, Conversation())
    try:
        resultat = conversation.poser(demande.question)
    except Exception as erreur:
        raise HTTPException(status_code=503, detail=f"Le modèle ne répond pas (Ollama est-il lancé ?) : {erreur}")
    return {
        "session_id": session_id,
        "question": resultat["question"],
        "question_comprise": resultat["question_recherche"],
        "reponse": resultat["reponse"],
        "sources": [
            {
                "fichier": s["fichier"],
                "ligne_debut": s["ligne_debut"],
                "ligne_fin": s["ligne_fin"],
                "nom": s["nom"],
                "extrait": "\n".join(s["code"].splitlines()[:3]),
            }
            for s in resultat["sources"]
        ],
        "duree": resultat["duree"],
    }


if __name__ == "__main__":
    print(f"CodeLocate AI : documentation sur http://{HOTE}:{PORT}/docs")
    uvicorn.run(app, host=HOTE, port=PORT)