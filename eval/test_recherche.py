"""Pose les questions de test et compare les méthodes de recherche.

Pour chaque méthode : le fichier attendu est-il dans les 5 résultats, et à quelle position ?

Usage : python -m eval.test_recherche
"""
import time
from pathlib import Path

from recherche.hybride import rechercher_hybride
from recherche.mots_cles import rechercher_par_mots_cles
from recherche.semantique import rechercher_par_sens

FICHIER_QUESTIONS = Path(__file__).with_name("questions_test.md")

METHODES = {
    "Sens seul": rechercher_par_sens,
    "Mots-clés seuls": rechercher_par_mots_cles,
    "Combinée": rechercher_hybride,
}


def charger_questions(chemin=FICHIER_QUESTIONS):
    """Lit le tableau Markdown et retourne une liste de (question, fichier attendu)."""
    questions = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        cellules = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if len(cellules) >= 3 and cellules[0].isdigit():
            questions.append((cellules[1], cellules[2]))
    return questions


def evaluer(fonction_recherche, questions):
    """Retourne la position du fichier attendu pour chaque question (None si absent) et la durée moyenne."""
    positions, duree_totale = [], 0.0
    for question, attendu in questions:
        depart = time.perf_counter()
        fichiers = [r["fichier"] for r in fonction_recherche(question)]
        duree_totale += time.perf_counter() - depart
        positions.append(fichiers.index(attendu) + 1 if attendu in fichiers else None)
    return positions, duree_totale / len(questions)


if __name__ == "__main__":
    questions = charger_questions()
    for numero, (question, attendu) in enumerate(questions, 1):
        print(f"Q{numero}. {question}  ->  {attendu}")

    print(f"\n{'Méthode':<17}" + "".join(f"Q{i:<5}" for i in range(1, len(questions) + 1))
          + "Score   1re place   Temps")
    for nom, fonction in METHODES.items():
        positions, duree = evaluer(fonction, questions)
        cases = "".join(f"{(str(p) if p else '-'):<6}" for p in positions)
        trouves = sum(p is not None for p in positions)
        premiers = sum(p == 1 for p in positions)
        print(f"{nom:<17}{cases}{trouves}/{len(questions)}     {premiers}/{len(questions)}         {duree:.2f} s")
    print("\nLes chiffres sous Q1, Q2... sont la position du bon fichier (1 = en tête, - = absent).")