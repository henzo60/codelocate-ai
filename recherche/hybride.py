"""Recherche combinée : fusionne la recherche par le sens et la recherche par mots-clés.

On garde les 5 meilleurs morceaux trouvés par le sens ET les 3 meilleurs trouvés par mots-clés,
pour qu'un bon morceau trouvé par une seule des deux méthodes ne soit jamais perdu.
Ils sont ensuite classés par la méthode RRF (Reciprocal Rank Fusion) : un morceau bien classé
dans les deux listes remonte en tête.

Usage : python -m recherche.hybride "ta question"
"""
import sys

import config
from recherche.mots_cles import rechercher_par_mots_cles
from recherche.semantique import afficher_resultats, rechercher_par_sens

K_RRF = 60  # valeur standard : atténue l'écart entre la 1re et la 2e place
NB_CANDIDATS = 10  # nombre de résultats demandés à chaque méthode pour calculer le classement
NB_MOTS_CLES = 3  # meilleurs résultats par mots-clés toujours gardés


def rechercher_hybride(question, nb_sens=config.NB_RESULTATS, nb_mots_cles=NB_MOTS_CLES):
    """Les meilleurs morceaux des deux méthodes réunies, du plus au moins pertinent."""
    par_sens = rechercher_par_sens(question, NB_CANDIDATS)
    par_mots_cles = rechercher_par_mots_cles(question, NB_CANDIDATS)

    points, morceaux = {}, {}
    for liste in (par_sens, par_mots_cles):
        for rang, morceau in enumerate(liste, 1):
            points[morceau["id"]] = points.get(morceau["id"], 0) + 1 / (K_RRF + rang)
            morceaux.setdefault(morceau["id"], morceau)

    retenus = {m["id"] for m in par_sens[:nb_sens]} | {m["id"] for m in par_mots_cles[:nb_mots_cles]}
    classement = sorted(retenus, key=points.get, reverse=True)
    return [dict(morceaux[i], score=round(points[i] * 1000, 1)) for i in classement]


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or input("Question : ")
    print(f"Question : {question}\n")
    afficher_resultats(rechercher_hybride(question))