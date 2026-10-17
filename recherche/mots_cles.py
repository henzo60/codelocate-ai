"""Recherche par mots-clés (BM25) : retrouve les noms exacts de fonctions, classes et variables.

Usage : python -m recherche.mots_cles "ta question"
"""
import re
import sys
import unicodedata

from rank_bm25 import BM25Okapi

import config
from indexation.indexeur import obtenir_collection

# Petits mots trop fréquents pour aider à trouver le bon code
MOTS_VIDES = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "en", "est", "que", "qui",
    "quoi", "dans", "par", "pour", "sur", "avec", "ce", "cet", "cette", "ces", "se", "sa", "son",
    "ses", "il", "elle", "on", "ne", "pas", "au", "aux", "fait", "faire", "comment", "quand",
    "quel", "quelle", "quels", "quelles", "ou", "fonction", "the", "self", "return", "def",
}

_cache = {}


def normaliser(texte):
    """Minuscules et sans accents : « Pénalité » devient « penalite », comme dans le code."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accents.lower()


def decouper_en_mots(texte):
    """Découpe un texte en mots, en gardant les noms composés et leurs parties.

    « calculer_penalite » donne : calculer_penalite, calculer, penalite.
    « GestionnaireSessions » donne : gestionnaire_sessions, gestionnaire, sessions.
    """
    texte = re.sub(r"([a-z])([A-Z])", r"\1_\2", texte)  # camelCase -> camel_Case
    mots = []
    for mot in re.findall(r"[a-z0-9_]+", normaliser(texte)):
        mot = mot.strip("_")
        if len(mot) < 2 or mot in MOTS_VIDES:
            continue
        mots.append(mot)
        if "_" in mot:
            mots.extend(p for p in mot.split("_") if len(p) >= 2 and p not in MOTS_VIDES)
    return mots


def charger_index():
    """Construit l'index BM25 à partir des morceaux déjà stockés dans ChromaDB (une seule fois)."""
    collection = obtenir_collection()
    if collection is None:
        raise RuntimeError(
            "La base est vide : indexe d'abord un projet avec "
            "python -m indexation.indexeur <dossier_du_projet>"
        )
    cle = (collection.metadata.get("projet"), collection.count())
    if _cache.get("cle") != cle:
        donnees = collection.get(include=["documents", "metadatas"])
        morceaux = [
            {
                "id": id_,
                "fichier": meta["fichier"],
                "ligne_debut": meta["ligne_debut"],
                "ligne_fin": meta["ligne_fin"],
                "nom": meta["nom"],
                "type": meta["type"],
                "code": code,
            }
            for id_, code, meta in zip(donnees["ids"], donnees["documents"], donnees["metadatas"])
        ]
        textes = [
            decouper_en_mots(f"{m['nom']} {m['fichier']} {meta.get('docstring', '')} {m['code']}")
            for m, meta in zip(morceaux, donnees["metadatas"])
        ]
        _cache.update(cle=cle, morceaux=morceaux, bm25=BM25Okapi(textes))
    return _cache["morceaux"], _cache["bm25"]


def rechercher_par_mots_cles(question, nb_resultats=config.NB_RESULTATS):
    """Les morceaux qui contiennent le plus les mots de la question (noms exacts compris)."""
    morceaux, bm25 = charger_index()
    mots = decouper_en_mots(question)
    if not mots:
        return []
    scores = bm25.get_scores(mots)
    classement = sorted(range(len(morceaux)), key=lambda i: scores[i], reverse=True)
    return [
        dict(morceaux[i], score=round(float(scores[i]), 2))
        for i in classement[:nb_resultats]
        if scores[i] > 0
    ]


if __name__ == "__main__":
    from recherche.semantique import afficher_resultats

    question = " ".join(sys.argv[1:]) or input("Question : ")
    print(f"Question : {question}")
    print(f"Mots recherchés : {', '.join(decouper_en_mots(question))}\n")
    afficher_resultats(rechercher_par_mots_cles(question))