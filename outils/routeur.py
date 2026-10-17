"""Aiguillage des questions : selon la question, on ajoute au contexte des résultats calculés exactement.

- Question de statistiques (« combien de fonctions ? », « la fonction la plus longue ») -> outil de statistiques
- Question sur les appels (« qui appelle calculer_penalite ? ») -> outil qui liste les appelants
- Sinon -> recherche combinée habituelle
"""
import re
import unicodedata
from pathlib import Path

from indexation.indexeur import obtenir_collection
from outils.analyse import (
    morceau_contenant,
    noms_de_fonctions,
    statistiques_projet,
    texte_statistiques,
    trouver_appelants,
)
from recherche.hybride import rechercher_hybride

MOTIF_STATISTIQUES = re.compile(r"\b(combien|nombre|statistiques?|stats|plus longues?|plus complexes?|taille)\b")
MOTIF_STRUCTURE = re.compile(r"\b(fichiers?|fonctions?|classes?|methodes?|lignes?|projet|code)\b")
MOTIF_APPELS = re.compile(r"\b(appell?e|appellent|appelees?|appels?|utilise|utilisent|utilisees?)\b")
MAX_APPELANTS = 6  # nombre maximum de fonctions appelantes dont on envoie le code au modèle


def _normaliser(texte):
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()


def dossier_projet():
    """Dossier du projet indexé, enregistré dans la base au moment de l'indexation."""
    collection = obtenir_collection()
    if collection is None:
        raise RuntimeError("La base est vide : indexe d'abord un projet.")
    return Path(collection.metadata["projet"])


def est_question_statistiques(question):
    """Vrai pour « combien de fonctions ? », mais pas pour « combien coûte un jour de retard ? »."""
    texte = _normaliser(question)
    return bool(MOTIF_STATISTIQUES.search(texte) and MOTIF_STRUCTURE.search(texte))


def fonction_appelee(question, dossier):
    """Nom de la fonction dont on cherche les appelants, ou None si ce n'est pas la question."""
    if not MOTIF_APPELS.search(_normaliser(question)):
        return None
    noms = noms_de_fonctions(dossier)
    for mot in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", question):
        if len(mot) > 2 and mot in noms:
            return mot
    return None


def _en_resultat(morceau):
    """Convertit un morceau du découpage au même format que les résultats de recherche."""
    return {
        "id": morceau.id,
        "fichier": morceau.fichier,
        "ligne_debut": morceau.ligne_debut,
        "ligne_fin": morceau.ligne_fin,
        "nom": morceau.nom_complet,
        "type": morceau.type,
        "code": morceau.code,
    }


def _ajouter(resultats, morceau):
    if morceau and all(r["id"] != morceau.id for r in resultats):
        resultats.append(_en_resultat(morceau))


def preparer_contexte(question):
    """Retourne (morceaux de code à montrer au modèle, texte calculé par un outil ou "")."""
    dossier = dossier_projet()

    if est_question_statistiques(question):
        stats = statistiques_projet(dossier)
        resultats = []
        for f in stats["plus_longues"] + stats["plus_complexes"]:
            _ajouter(resultats, morceau_contenant(dossier, f["fichier"], f["ligne_debut"]))
        texte = "Statistiques du projet calculées par l'outil d'analyse :\n" + texte_statistiques(stats)
        return resultats, texte

    resultats = rechercher_hybride(question)
    nom = fonction_appelee(question, dossier)
    if not nom:
        return resultats, ""

    appels = sorted(trouver_appelants(dossier, nom), key=lambda a: a["fichier"].startswith("tests/"))
    appelants, lignes = [], []
    for appel in appels:
        morceau = morceau_contenant(dossier, appel["fichier"], appel["ligne"])
        if len(appelants) < MAX_APPELANTS:
            _ajouter(appelants, morceau)
        citation = f" [{morceau.fichier}:{morceau.ligne_debut}-{morceau.ligne_fin}]" if morceau else ""
        lignes.append(f"- {appel['fichier']}, ligne {appel['ligne']}, dans {appel['appelant']}{citation}")
    texte = (
        f"Appels de la fonction {nom} trouvés par l'outil d'analyse "
        f"(liste complète : {len(appels)} appel(s)) :\n" + ("\n".join(lignes) or "- aucun appel trouvé")
    )
    ids = {r["id"] for r in appelants}
    return appelants + [r for r in resultats if r["id"] not in ids], texte