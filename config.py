"""Réglages centraux de CodeLocate AI."""
from pathlib import Path

# Modèles Ollama
MODELE_LLM = "qwen2.5-coder:7b"
MODELE_EMBEDDING = "nomic-embed-text"

# Base vectorielle ChromaDB (enregistrée sur le disque)
DOSSIER_RACINE = Path(__file__).resolve().parent
DOSSIER_CHROMA = DOSSIER_RACINE / "data" / "chroma"
NOM_COLLECTION = "codelocate"

# Indexation et recherche
TAILLE_LOT = 16  # nombre de morceaux envoyés à Ollama en une fois
NB_RESULTATS = 5