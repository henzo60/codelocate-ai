"""Le chatbot : retrouve le code utile, puis demande à Qwen2.5-Coder une réponse qui cite ses sources.

Usage : python -m chatbot.reponse "ta question"
"""
import re
import sys
import time

import ollama

import config
from outils.routeur import preparer_contexte

TAILLE_CONTEXTE = 8192  # nombre de tokens que le modèle peut lire en une fois
PHRASE_INCONNU = "Je ne sais pas : le code fourni ne contient pas la réponse."
RAPPEL_FORMAT = "Cite chaque source au format [fichier:début-fin], avec les numéros de ligne affichés."

PROMPT_SYSTEME = f"""Tu es CodeLocate AI, un assistant qui aide un développeur à comprendre un projet Python.

Règles à respecter absolument :
1. Réponds uniquement à partir des extraits de code fournis. N'invente rien.
2. Après chaque information importante, cite sa source entre crochets au format [fichier:début-fin].
   Les numéros de ligne sont écrits au début de chaque ligne de code : utilise-les.
3. Si les extraits ne permettent pas de répondre, réponds uniquement : « {PHRASE_INCONNU} »
4. Réponds en français, de façon claire et concise (10 phrases maximum).
5. Si une section « Résultats de l'outil d'analyse » est fournie, elle est exacte et complète :
   appuie-toi d'abord sur elle, recopie ses chiffres sans les modifier et cite ses sources.

Exemple de réponse bien citée :
La pénalité est gratuite pendant les premiers jours de retard [services/penalites.py:12-14],
puis elle augmente chaque jour sans dépasser un plafond [services/penalites.py:15-16]."""

MOTIF_CITATION = re.compile(r"([\w./-]+\.py):(\d+)(?:\s*-\s*(\d+))?")


def extraire_citations(texte):
    """Toutes les citations fichier:début-fin du texte, même groupées ou sur une seule ligne."""
    citations = []
    for fichier, debut, fin in MOTIF_CITATION.findall(texte):
        citation = (fichier, int(debut), int(fin or debut))
        if citation not in citations:
            citations.append(citation)
    return citations


def code_numerote(resultat):
    """Code d'un morceau avec le numéro de ligne réel devant chaque ligne.

    Seules les fonctions et méthodes sont numérotées : leur code est un bloc continu du fichier.
    """
    lignes = resultat["code"].splitlines()
    if resultat["type"] not in ("fonction", "methode"):
        return "\n".join(lignes)
    return "\n".join(
        f"{resultat['ligne_debut'] + i:>4} | {ligne}" for i, ligne in enumerate(lignes)
    )


def assembler_contexte(resultats, texte_outil=""):
    """Met bout à bout les morceaux trouvés, chacun précédé de son fichier et de ses lignes.

    Si un outil a calculé un résultat exact, il est placé en premier.
    """
    blocs = [f"### Résultats de l'outil d'analyse (exacts)\n{texte_outil}"] if texte_outil else []
    for r in resultats:
        blocs.append(
            f"### Fichier {r['fichier']}, lignes {r['ligne_debut']}-{r['ligne_fin']} "
            f"({r['type']} {r['nom']})\n{code_numerote(r)}"
        )
    return "\n\n".join(blocs)


def construire_messages(question, contexte):
    return [
        {"role": "system", "content": PROMPT_SYSTEME},
        {
            "role": "user",
            "content": f"Extraits de code :\n\n{contexte}\n\nQuestion : {question}\n\n{RAPPEL_FORMAT}",
        },
    ]


def trouver_source(citation, resultats):
    """Le morceau fourni qui contient la citation (même fichier, lignes comprises dans le morceau)."""
    fichier, debut, fin = citation
    for r in resultats:
        if r["fichier"] == fichier and r["ligne_debut"] <= debut <= fin <= r["ligne_fin"]:
            return r
    return None


def sources_citees(texte, resultats):
    """Les morceaux réellement cités dans la réponse (tous les morceaux si aucune citation n'est lisible)."""
    if PHRASE_INCONNU.lower().rstrip(".") in texte.lower():
        return []
    cites = []
    for citation in extraire_citations(texte):
        source = trouver_source(citation, resultats)
        if source and source not in cites:
            cites.append(source)
    return cites or resultats


def interroger_modele(messages, en_direct=False):
    """Envoie les messages à Qwen2.5-Coder et retourne sa réponse.

    En direct (streaming), le texte s'affiche au fur et à mesure qu'il est écrit.
    """
    morceaux = []
    flux = ollama.chat(
        model=config.MODELE_LLM,
        messages=messages,
        options={"temperature": 0.1, "num_ctx": TAILLE_CONTEXTE},
        stream=True,
    )
    for partie in flux:
        texte = partie["message"]["content"]
        morceaux.append(texte)
        if en_direct:
            print(texte, end="", flush=True)
    if en_direct:
        print()
    return "".join(morceaux).strip()


def repondre(question, en_direct=False):
    """Pose la question au chatbot et retourne la réponse, ses sources et sa durée."""
    depart = time.perf_counter()
    resultats, texte_outil = preparer_contexte(question)
    messages = construire_messages(question, assembler_contexte(resultats, texte_outil))
    texte = interroger_modele(messages, en_direct)
    return {
        "question": question,
        "reponse": texte,
        "resultats": resultats,
        "sources": sources_citees(texte, resultats),
        "duree": round(time.perf_counter() - depart, 1),
    }


def afficher(resultat, reponse_deja_affichee=False):
    """Affiche la réponse (sauf si elle est déjà apparue en direct), puis ses sources."""
    if not reponse_deja_affichee:
        print(resultat["reponse"])
    if resultat["sources"]:
        print("\nSources :")
        for s in resultat["sources"]:
            extrait = s["code"].splitlines()[0].strip()
            print(f"  - {s['fichier']}, lignes {s['ligne_debut']}-{s['ligne_fin']} : {extrait}")
    print(f"\n(répondu en {resultat['duree']} s)")


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or input("Question : ")
    print(f"Question : {question}\n")
    afficher(repondre(question, en_direct=True), reponse_deja_affichee=True)