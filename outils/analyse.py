"""Outils de calcul sur le code : réponses exactes calculées avec ast, sans laisser le modèle deviner.

- statistiques_projet : fichiers, lignes, fonctions, classes, fonctions les plus longues et complexes
- trouver_appelants : tous les endroits où une fonction est appelée

Usage :
    python -m outils.analyse stats <dossier_du_projet>
    python -m outils.analyse appelants <nom_de_fonction> <dossier_du_projet>
"""
import ast
import sys
from pathlib import Path

from indexation.decoupage import decouper_projet, lister_fichiers_python

# Chaque branche (if, boucle, except...) ajoute un chemin possible dans la fonction
NOEUDS_BRANCHES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
    ast.IfExp, ast.comprehension, ast.Assert, ast.match_case,
)


def complexite(noeud):
    """Complexité cyclomatique : 1 + nombre de branches et de conditions combinées (and / or)."""
    total = 1
    for enfant in ast.walk(noeud):
        if isinstance(enfant, NOEUDS_BRANCHES):
            total += 1
        elif isinstance(enfant, ast.BoolOp):
            total += len(enfant.values) - 1
    return total


def _fonctions_du_fichier(arbre):
    """Fonctions et méthodes de premier niveau, avec le nom de leur classe éventuelle."""
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield noeud, ""
        elif isinstance(noeud, ast.ClassDef):
            for enfant in noeud.body:
                if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield enfant, noeud.name


def _lire_arbres(dossier):
    """(chemin relatif, lignes du fichier, arbre ast) pour chaque fichier Python lisible."""
    racine = Path(dossier).resolve()
    for chemin in lister_fichiers_python(racine):
        try:
            source = chemin.read_text(encoding="utf-8")
            arbre = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue
        yield chemin.relative_to(racine).as_posix(), source.splitlines(), arbre


def statistiques_projet(dossier, top=5):
    """Chiffres exacts sur le projet, calculés en lisant chaque fichier."""
    stats = {"fichiers": 0, "lignes": 0, "lignes_code": 0,
             "fonctions": 0, "methodes": 0, "classes": 0}
    fonctions = []
    for fichier, lignes, arbre in _lire_arbres(dossier):
        stats["fichiers"] += 1
        stats["lignes"] += len(lignes)
        stats["lignes_code"] += sum(
            1 for l in lignes if l.strip() and not l.strip().startswith("#")
        )
        stats["classes"] += sum(isinstance(n, ast.ClassDef) for n in ast.walk(arbre))
        for noeud, classe in _fonctions_du_fichier(arbre):
            stats["methodes" if classe else "fonctions"] += 1
            debut = min([noeud.lineno] + [d.lineno for d in noeud.decorator_list])
            fonctions.append({
                "nom": f"{classe}.{noeud.name}" if classe else noeud.name,
                "fichier": fichier,
                "ligne_debut": debut,
                "ligne_fin": noeud.end_lineno,
                "longueur": noeud.end_lineno - debut + 1,
                "complexite": complexite(noeud),
            })
    stats["plus_longues"] = sorted(fonctions, key=lambda f: -f["longueur"])[:top]
    stats["plus_complexes"] = sorted(fonctions, key=lambda f: -f["complexite"])[:top]
    return stats


def _nom_appele(appel):
    """Nom de la fonction appelée : f(...) -> f, objet.f(...) -> f."""
    if isinstance(appel.func, ast.Name):
        return appel.func.id
    if isinstance(appel.func, ast.Attribute):
        return appel.func.attr
    return None


def trouver_appelants(dossier, nom):
    """Tous les appels à la fonction `nom` : fichier, ligne de l'appel et fonction qui appelle."""
    appels = []
    for fichier, _, arbre in _lire_arbres(dossier):
        for noeud, classe in _fonctions_du_fichier(arbre):
            for enfant in ast.walk(noeud):
                if isinstance(enfant, ast.Call) and _nom_appele(enfant) == nom:
                    appels.append({
                        "fichier": fichier,
                        "ligne": enfant.lineno,
                        "appelant": f"{classe}.{noeud.name}" if classe else noeud.name,
                    })
    return appels


def noms_de_fonctions(dossier):
    """Ensemble des noms de fonctions et méthodes définies dans le projet."""
    return {
        noeud.name
        for _, _, arbre in _lire_arbres(dossier)
        for noeud, _ in _fonctions_du_fichier(arbre)
    }


def morceaux_du_projet(dossier, _cache={}):
    """Les morceaux du projet (découpés une seule fois), pour retrouver le code d'un appelant."""
    cle = str(Path(dossier).resolve())
    if cle not in _cache:
        _cache[cle] = decouper_projet(dossier)
    return _cache[cle]


def morceau_contenant(dossier, fichier, ligne):
    """La fonction ou méthode qui contient une ligne donnée d'un fichier."""
    for m in morceaux_du_projet(dossier):
        if m.fichier == fichier and m.type in ("fonction", "methode") and m.ligne_debut <= ligne <= m.ligne_fin:
            return m
    return None


def texte_statistiques(stats):
    """Les statistiques rédigées en texte, avec des citations [fichier:début-fin]."""
    lignes = [
        f"- Fichiers Python : {stats['fichiers']}",
        f"- Lignes au total : {stats['lignes']} (dont {stats['lignes_code']} lignes de code, "
        "sans les lignes vides ni les commentaires)",
        f"- Fonctions : {stats['fonctions']} | Méthodes : {stats['methodes']} | Classes : {stats['classes']}",
        "",
        "Fonctions les plus longues :",
    ]
    for i, f in enumerate(stats["plus_longues"], 1):
        lignes.append(f"{i}. {f['nom']} [{f['fichier']}:{f['ligne_debut']}-{f['ligne_fin']}] : {f['longueur']} lignes")
    lignes += ["", "Fonctions les plus complexes (complexité cyclomatique = nombre de chemins possibles) :"]
    for i, f in enumerate(stats["plus_complexes"], 1):
        lignes.append(f"{i}. {f['nom']} [{f['fichier']}:{f['ligne_debut']}-{f['ligne_fin']}] : {f['complexite']}")
    return "\n".join(lignes)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "stats":
        print(texte_statistiques(statistiques_projet(sys.argv[2])))
    elif len(sys.argv) >= 4 and sys.argv[1] == "appelants":
        nom, dossier = sys.argv[2], sys.argv[3]
        appels = trouver_appelants(dossier, nom)
        print(f"{nom} est appelée {len(appels)} fois :")
        for a in appels:
            print(f"  - {a['fichier']}, ligne {a['ligne']}, dans {a['appelant']}")
    else:
        print(__doc__)