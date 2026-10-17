"""Vérification des citations : chaque source citée par le chatbot correspond-elle au code réel ?

Pose les questions de test, puis contrôle chaque citation [fichier:début-fin] des réponses.

Usage : python -m chatbot.citations
"""
from pathlib import Path

from chatbot.reponse import extraire_citations, repondre, trouver_source
from eval.test_recherche import charger_questions
from indexation.indexeur import obtenir_collection


def dossier_projet():
    """Dossier du projet indexé, enregistré dans la base au moment de l'indexation."""
    collection = obtenir_collection()
    if collection is None:
        raise RuntimeError("La base est vide : indexe d'abord un projet.")
    return Path(collection.metadata["projet"])


def citations_dans_texte(texte):
    """Toutes les citations [fichier:début-fin] trouvées dans une réponse."""
    return extraire_citations(texte)


def verifier_citation(citation, resultats, dossier):
    """Retourne None si la citation est correcte, sinon une phrase qui explique le problème."""
    fichier, debut, fin = citation
    source = trouver_source(citation, resultats)
    if source is None:
        return "citation inventée : ces lignes ne font pas partie du code fourni au modèle"
    chemin = dossier / fichier
    if not chemin.exists():
        return "fichier introuvable dans le projet"
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    if fin > len(lignes):
        return "les lignes citées dépassent la fin du fichier"
    if lignes[source["ligne_debut"] - 1].strip() != source["code"].splitlines()[0].strip():
        return "le code a changé depuis l'indexation (réindexe le projet)"
    return None


if __name__ == "__main__":
    dossier = dossier_projet()
    total, correctes, attendus_cites = 0, 0, 0
    questions = charger_questions()

    for numero, (question, attendu) in enumerate(questions, 1):
        resultat = repondre(question)
        print(f"\nQ{numero}. {question}  ({resultat['duree']} s)")
        print("-" * 70)
        print(resultat["reponse"])
        print("-" * 70)

        citations = citations_dans_texte(resultat["reponse"])
        if not citations:
            print("   Aucune citation au format [fichier:début-fin] dans la réponse.")
        for citation in dict.fromkeys(citations):
            total += 1
            probleme = verifier_citation(citation, resultat["resultats"], dossier)
            etiquette = f"{citation[0]}:{citation[1]}-{citation[2]}"
            if probleme:
                print(f"   PROBLÈME : {etiquette} -> {probleme}")
            else:
                correctes += 1
                print(f"   OK       : {etiquette} correspond au code réel")
        if any(c[0] == attendu for c in citations):
            attendus_cites += 1

    print(f"\nCitations correctes : {correctes}/{total}")
    print(f"Fichier attendu cité : {attendus_cites}/{len(questions)} questions")