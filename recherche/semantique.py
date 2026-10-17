"""Recherche par le sens : retrouve les morceaux de code les plus proches d'une question.

Usage : python -m recherche.semantique "ta question"
"""
import sys

import ollama

import config
from indexation.indexeur import obtenir_collection

# nomic-embed-text attend ce préfixe devant une question (et « search_document: » devant le code)
PREFIXE_QUESTION = "search_query: "


def vectoriser_question(question):
    """Transforme la question en vecteur, avec le même modèle que celui utilisé pour le code."""
    reponse = ollama.embed(model=config.MODELE_EMBEDDING, input=[PREFIXE_QUESTION + question])
    return reponse["embeddings"][0]


def rechercher_par_sens(question, nb_resultats=config.NB_RESULTATS):
    """Retourne les morceaux les plus proches de la question, du plus proche au moins proche."""
    collection = obtenir_collection()
    if collection is None:
        raise RuntimeError(
            "La base est vide : indexe d'abord un projet avec "
            "python -m indexation.indexeur <dossier_du_projet>"
        )
    resultat = collection.query(
        query_embeddings=[vectoriser_question(question)],
        n_results=nb_resultats,
    )
    morceaux = []
    for id_, code, meta, distance in zip(
        resultat["ids"][0],
        resultat["documents"][0],
        resultat["metadatas"][0],
        resultat["distances"][0],
    ):
        morceaux.append(
            {
                "id": id_,
                "fichier": meta["fichier"],
                "ligne_debut": meta["ligne_debut"],
                "ligne_fin": meta["ligne_fin"],
                "nom": meta["nom"],
                "type": meta["type"],
                "code": code,
                "score": round(1 - distance, 3),  # 1 = identique, 0 = sans rapport
            }
        )
    return morceaux


def afficher_resultats(resultats):
    for rang, r in enumerate(resultats, 1):
        print(
            f"{rang}. {r['fichier']} (lignes {r['ligne_debut']}-{r['ligne_fin']}) "
            f"{r['type']} {r['nom']}  [score {r['score']}]"
        )


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or input("Question : ")
    print(f"Question : {question}\n")
    afficher_resultats(rechercher_par_sens(question))