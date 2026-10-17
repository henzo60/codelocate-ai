"""Pose les questions de test et vérifie que le fichier attendu fait partie des résultats.

Usage : python -m eval.test_recherche
"""
import time
from pathlib import Path

from recherche.semantique import rechercher_par_sens

FICHIER_QUESTIONS = Path(__file__).with_name("questions_test.md")


def charger_questions(chemin=FICHIER_QUESTIONS):
    """Lit le tableau Markdown et retourne une liste de (question, fichier attendu)."""
    questions = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        cellules = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if len(cellules) >= 3 and cellules[0].isdigit():
            questions.append((cellules[1], cellules[2]))
    return questions


def evaluer(fonction_recherche=rechercher_par_sens):
    """Affiche, question par question, si le bon fichier est trouvé et à quelle position."""
    questions = charger_questions()
    reussites = 0
    duree_totale = 0.0
    for numero, (question, attendu) in enumerate(questions, 1):
        depart = time.perf_counter()
        resultats = fonction_recherche(question)
        duree_totale += time.perf_counter() - depart

        fichiers = [r["fichier"] for r in resultats]
        print(f"Q{numero}. {question}")
        if attendu in fichiers:
            reussites += 1
            print(f"   OK   : {attendu} trouvé en position {fichiers.index(attendu) + 1}")
        else:
            print(f"   RATÉ : {attendu} absent. Trouvés : {', '.join(dict.fromkeys(fichiers))}")

    print(f"\nScore : {reussites}/{len(questions)} questions avec le bon fichier dans les résultats")
    print(f"Temps moyen par recherche : {duree_totale / len(questions):.2f} s")
    return reussites


if __name__ == "__main__":
    evaluer()