"""Transformation des morceaux de code en vecteurs et stockage dans ChromaDB.

Usage :
    python -m indexation.indexeur <dossier_du_projet>   # indexe (ou réindexe) un projet
    python -m indexation.indexeur --info                # affiche ce que contient la base
"""
import argparse
import time
from pathlib import Path

import chromadb
import ollama

import config
from indexation.decoupage import decouper_projet

# nomic-embed-text attend un préfixe qui précise si le texte est un document ou une question
PREFIXE_DOCUMENT = "search_document: "


def ouvrir_base():
    """Ouvre la base ChromaDB enregistrée dans data/chroma (créée au premier appel)."""
    return chromadb.PersistentClient(path=str(config.DOSSIER_CHROMA))


def obtenir_collection():
    """Retourne la collection du projet indexé, ou None si rien n'a encore été indexé."""
    client = ouvrir_base()
    try:
        return client.get_collection(config.NOM_COLLECTION)
    except Exception:
        return None


def creer_embeddings(textes):
    """Envoie une liste de textes à nomic-embed-text et retourne un vecteur par texte."""
    reponse = ollama.embed(
        model=config.MODELE_EMBEDDING,
        input=[PREFIXE_DOCUMENT + texte for texte in textes],
    )
    return reponse["embeddings"]


def metadonnees(morceau):
    """Informations stockées à côté du vecteur, pour pouvoir citer la source."""
    return {
        "fichier": morceau.fichier,
        "ligne_debut": morceau.ligne_debut,
        "ligne_fin": morceau.ligne_fin,
        "type": morceau.type,
        "nom": morceau.nom_complet,
        "docstring": morceau.docstring[:500],
    }


def indexer_projet(dossier):
    """Découpe le projet, crée un vecteur par morceau et remplace le contenu de la base."""
    dossier = Path(dossier).resolve()
    morceaux = decouper_projet(dossier)
    if not morceaux:
        raise ValueError(f"Aucun code Python trouvé dans {dossier}")

    client = ouvrir_base()
    try:
        client.delete_collection(config.NOM_COLLECTION)  # on repart de zéro
    except Exception:
        pass
    collection = client.create_collection(
        name=config.NOM_COLLECTION,
        metadata={"hnsw:space": "cosine", "projet": str(dossier)},
    )

    for debut in range(0, len(morceaux), config.TAILLE_LOT):
        lot = morceaux[debut : debut + config.TAILLE_LOT]
        collection.add(
            ids=[m.id for m in lot],
            embeddings=creer_embeddings([m.texte_pour_embedding() for m in lot]),
            documents=[m.code for m in lot],
            metadatas=[metadonnees(m) for m in lot],
        )
        print(f"  {min(debut + len(lot), len(morceaux))}/{len(morceaux)} morceaux indexés")
    return collection


def afficher_infos():
    collection = obtenir_collection()
    if collection is None:
        print("La base est vide : lance d'abord l'indexation d'un projet.")
        return
    print(f"Projet indexé : {collection.metadata.get('projet')}")
    print(f"Morceaux en base : {collection.count()}")
    print(f"Base enregistrée dans : {config.DOSSIER_CHROMA}")


if __name__ == "__main__":
    parseur = argparse.ArgumentParser(description="Indexation d'un projet Python")
    parseur.add_argument("dossier", nargs="?", help="dossier du projet à indexer")
    parseur.add_argument("--info", action="store_true", help="affiche le contenu de la base")
    arguments = parseur.parse_args()

    if arguments.info or not arguments.dossier:
        afficher_infos()
    else:
        depart = time.perf_counter()
        print(f"Indexation de {Path(arguments.dossier).resolve()} ...")
        collection = indexer_projet(arguments.dossier)
        duree = time.perf_counter() - depart
        print(f"Terminé : {collection.count()} morceaux indexés en {duree:.1f} secondes.")
        print(f"Base enregistrée dans : {config.DOSSIER_CHROMA}")