"""Découpage d'un projet Python en morceaux : une fonction, une méthode ou une classe par morceau.

Chaque morceau garde son fichier et ses lignes exactes, pour que le chatbot
puisse citer ses sources.

Usage : python -m indexation.decoupage <dossier_du_projet>
"""
import ast
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

DOSSIERS_IGNORES = {".venv", "venv", "env", "__pycache__", ".git", "node_modules", "build", "dist"}


@dataclass
class Morceau:
    """Un bout de code isolé, avec tout ce qu'il faut pour le retrouver et le citer."""

    type: str  # "fonction", "methode", "classe" ou "module"
    nom: str
    fichier: str  # chemin relatif au projet, avec des « / »
    ligne_debut: int
    ligne_fin: int
    code: str
    docstring: str = ""
    classe_parente: str = ""

    @property
    def id(self):
        """Identifiant unique, par exemple « services/penalites.py:7-18 »."""
        return f"{self.fichier}:{self.ligne_debut}-{self.ligne_fin}"

    @property
    def nom_complet(self):
        return f"{self.classe_parente}.{self.nom}" if self.classe_parente else self.nom

    def texte_pour_embedding(self):
        """Texte enrichi (fichier, classe, docstring, code) qui sera transformé en vecteur."""
        entete = f"Fichier : {self.fichier} | {self.type.capitalize()} : {self.nom_complet}"
        morceaux = [entete]
        if self.docstring:
            morceaux.append(f"Description : {self.docstring}")
        morceaux.append(self.code)
        return "\n".join(morceaux)


def lister_fichiers_python(dossier):
    """Tous les fichiers .py du projet, sans les dossiers techniques (.venv, __pycache__...)."""
    racine = Path(dossier).resolve()
    fichiers = [
        chemin
        for chemin in racine.rglob("*.py")
        if not DOSSIERS_IGNORES.intersection(chemin.relative_to(racine).parts)
    ]
    return sorted(fichiers)


def _premiere_ligne(noeud):
    """Ligne de début d'une fonction ou d'une classe, en incluant ses décorateurs (@...)."""
    lignes = [noeud.lineno] + [decorateur.lineno for decorateur in noeud.decorator_list]
    return min(lignes)


def _extraire(lignes, debut, fin):
    """Lignes debut à fin (numérotées à partir de 1, fin incluse)."""
    return "\n".join(lignes[debut - 1 : fin])


def _morceau_classe(noeud, lignes, fichier):
    """Morceau d'une classe : son en-tête, sa docstring, ses attributs et la liste de ses méthodes.

    Le corps des méthodes n'est pas recopié, puisque chaque méthode a son propre morceau.
    """
    debut = _premiere_ligne(noeud)
    methodes = [n for n in noeud.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    fin_entete = _premiere_ligne(methodes[0]) - 1 if methodes else noeud.end_lineno
    code = _extraire(lignes, debut, fin_entete).rstrip()
    if methodes:
        code += "\n    # Méthodes : " + ", ".join(m.name for m in methodes)
    return Morceau(
        type="classe",
        nom=noeud.name,
        fichier=fichier,
        ligne_debut=debut,
        ligne_fin=noeud.end_lineno,
        code=code,
        docstring=ast.get_docstring(noeud) or "",
    )


def _morceau_fonction(noeud, lignes, fichier, classe_parente=""):
    debut = _premiere_ligne(noeud)
    return Morceau(
        type="methode" if classe_parente else "fonction",
        nom=noeud.name,
        fichier=fichier,
        ligne_debut=debut,
        ligne_fin=noeud.end_lineno,
        code=_extraire(lignes, debut, noeud.end_lineno),
        docstring=ast.get_docstring(noeud) or "",
        classe_parente=classe_parente,
    )


def _morceau_module(arbre, lignes, fichier):
    """Morceau regroupant le code « libre » du fichier (constantes, tables, variables globales).

    Retourne None si le fichier ne contient que des imports et des fonctions/classes.
    """
    noeuds = [
        n
        for n in arbre.body
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))
    ]
    docstring = ast.get_docstring(arbre) or ""
    if docstring:
        noeuds = noeuds[1:]  # le premier nœud est la docstring elle-même
    if not noeuds:
        return None
    blocs = [_extraire(lignes, n.lineno, n.end_lineno) for n in noeuds]
    return Morceau(
        type="module",
        nom=Path(fichier).stem,
        fichier=fichier,
        ligne_debut=noeuds[0].lineno,
        ligne_fin=noeuds[-1].end_lineno,
        code="\n".join(blocs),
        docstring=docstring,
    )


def decouper_fichier(chemin, racine):
    """Découpe un fichier .py en morceaux. Retourne une liste vide si le fichier est illisible."""
    fichier = Path(chemin).resolve().relative_to(Path(racine).resolve()).as_posix()
    try:
        source = Path(chemin).read_text(encoding="utf-8")
        arbre = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError) as erreur:
        print(f"[ignoré] {fichier} : {erreur}", file=sys.stderr)
        return []

    lignes = source.splitlines()
    morceaux = []
    module = _morceau_module(arbre, lignes, fichier)
    if module:
        morceaux.append(module)

    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            morceaux.append(_morceau_fonction(noeud, lignes, fichier))
        elif isinstance(noeud, ast.ClassDef):
            morceaux.append(_morceau_classe(noeud, lignes, fichier))
            for enfant in noeud.body:
                if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    morceaux.append(_morceau_fonction(enfant, lignes, fichier, noeud.name))
    return morceaux


def decouper_projet(dossier):
    """Découpe tous les fichiers .py d'un projet et retourne la liste de tous les morceaux."""
    morceaux = []
    for chemin in lister_fichiers_python(dossier):
        morceaux.extend(decouper_fichier(chemin, dossier))
    return morceaux


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage : python -m indexation.decoupage <dossier_du_projet>")
        sys.exit(1)

    dossier = sys.argv[1]
    fichiers = lister_fichiers_python(dossier)
    morceaux = decouper_projet(dossier)
    types = Counter(m.type for m in morceaux)

    print(f"{len(fichiers)} fichiers Python analysés")
    print(f"{len(morceaux)} morceaux extraits :")
    for type_, nombre in types.most_common():
        print(f"  - {type_} : {nombre}")

    print("\nExemple de morceau :")
    exemple = next((m for m in morceaux if m.nom == "calculer_penalite"), morceaux[0])
    print(f"  {exemple.id} ({exemple.type} {exemple.nom_complet})")
    print("-" * 60)
    print(exemple.texte_pour_embedding())