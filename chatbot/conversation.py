"""Conversation avec mémoire : le chatbot se souvient des derniers échanges.

Permet les questions de suivi comme « et qui appelle cette fonction ? ».

Usage : python -m chatbot.conversation
"""
import time

import ollama

import config
from chatbot.reponse import (
    PROMPT_SYSTEME,
    RAPPEL_FORMAT,
    afficher,
    assembler_contexte,
    interroger_modele,
    sources_citees,
)
from recherche.hybride import rechercher_hybride

MAX_ECHANGES = 3  # nombre d'échanges précédents gardés en mémoire
MAX_CARACTERES_HISTORIQUE = 6000  # environ 1 500 tokens, pour laisser la place au code

PROMPT_REFORMULATION = """Voici la fin d'une conversation entre un développeur et un assistant de code, puis une nouvelle question.
Réécris la nouvelle question pour qu'elle se comprenne seule : remplace les mots comme « cette fonction », « il », « ça » ou « ce fichier » par les noms précis (fonctions, classes, fichiers) cités dans la conversation.
Si la question se comprend déjà seule, recopie-la telle quelle.
Réponds uniquement avec la question réécrite, sans aucune explication."""


class Conversation:
    """Garde les derniers échanges et s'en sert pour comprendre les questions de suivi."""

    def __init__(self, max_echanges=MAX_ECHANGES, max_caracteres=MAX_CARACTERES_HISTORIQUE):
        self.max_echanges = max_echanges
        self.max_caracteres = max_caracteres
        self.echanges = []  # liste de (question, réponse)

    def effacer(self):
        self.echanges = []

    def historique(self):
        """Les derniers échanges, en retirant les plus anciens si le texte devient trop long."""
        recents = self.echanges[-self.max_echanges :]
        while recents and sum(len(q) + len(r) for q, r in recents) > self.max_caracteres:
            recents = recents[1:]
        return recents

    def question_autonome(self, question):
        """Réécrit une question de suivi pour qu'elle se comprenne sans la conversation."""
        historique = self.historique()
        if not historique:
            return question
        resume = "\n".join(
            f"Développeur : {q}\nAssistant : {r[:800]}" for q, r in historique[-2:]
        )
        reponse = ollama.chat(
            model=config.MODELE_LLM,
            messages=[
                {"role": "system", "content": PROMPT_REFORMULATION},
                {"role": "user", "content": f"Conversation :\n{resume}\n\nNouvelle question : {question}"},
            ],
            options={"temperature": 0, "num_ctx": 4096},
        )
        reecrite = reponse["message"]["content"].strip().strip('"«» ')
        # garde-fou : si la réécriture est vide ou délirante, on garde la question d'origine
        if not reecrite or len(reecrite) > 4 * len(question) + 200:
            return question
        return reecrite

    def poser(self, question, en_direct=False):
        """Répond à une question en tenant compte des échanges précédents."""
        depart = time.perf_counter()
        question_recherche = self.question_autonome(question)
        if en_direct and question_recherche != question:
            print(f"(question comprise comme : {question_recherche})\n")
        resultats = rechercher_hybride(question_recherche)

        messages = [{"role": "system", "content": PROMPT_SYSTEME}]
        for ancienne_question, ancienne_reponse in self.historique():
            messages.append({"role": "user", "content": ancienne_question})
            messages.append({"role": "assistant", "content": ancienne_reponse})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Extraits de code :\n\n{assembler_contexte(resultats)}\n\n"
                    f"Question : {question_recherche}\n\n{RAPPEL_FORMAT}"
                ),
            }
        )

        texte = interroger_modele(messages, en_direct)
        self.echanges.append((question, texte))
        return {
            "question": question,
            "question_recherche": question_recherche,
            "reponse": texte,
            "resultats": resultats,
            "sources": sources_citees(texte, resultats),
            "duree": round(time.perf_counter() - depart, 1),
        }


if __name__ == "__main__":
    conversation = Conversation()
    print("CodeLocate AI : pose tes questions sur le code.")
    print("Tape « nouveau » pour oublier la conversation, « quitter » pour sortir.\n")
    while True:
        try:
            question = input("Vous > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            continue
        if question.lower() in ("quitter", "exit", "q"):
            break
        if question.lower() == "nouveau":
            conversation.effacer()
            print("Conversation effacée.\n")
            continue
        print()
        resultat = conversation.poser(question, en_direct=True)
        afficher(resultat, reponse_deja_affichee=True)
        print()
    print("À bientôt !")