"""Interface web de CodeLocate AI (Streamlit).

La page discute avec l'API locale : lance d'abord le serveur dans un autre terminal.
    Terminal 1 : python -m api.serveur
    Terminal 2 : streamlit run app.py
"""
import json
import urllib.error
import urllib.request
from pathlib import Path

import streamlit as st

URL_API = "http://127.0.0.1:8000"


def appeler_api(route, donnees=None, delai=600):
    """Appelle l'API locale (GET sans données, POST avec). Retourne (réponse, message d'erreur)."""
    requete = urllib.request.Request(
        URL_API + route,
        data=json.dumps(donnees).encode("utf-8") if donnees is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if donnees is not None else "GET",
    )
    try:
        with urllib.request.urlopen(requete, timeout=delai) as reponse:
            return json.loads(reponse.read().decode("utf-8")), None
    except urllib.error.HTTPError as erreur:
        detail = json.loads(erreur.read().decode("utf-8")).get("detail", erreur.reason)
        return None, f"Erreur {erreur.code} : {detail}"
    except urllib.error.URLError:
        return None, "L'API ne répond pas. Lance-la dans un terminal : python -m api.serveur"


def lien_vscode(projet, source):
    """Lien qui ouvre le fichier cité dans VS Code, directement à la bonne ligne."""
    chemin = (Path(projet) / source["fichier"]).as_posix()
    return f"vscode://file/{chemin}:{source['ligne_debut']}"


def afficher_sources(sources, projet):
    if not sources:
        return
    st.markdown("**Sources**")
    for s in sources:
        titre = f"📄 {s['fichier']} — lignes {s['ligne_debut']}-{s['ligne_fin']} ({s['nom']})"
        with st.expander(titre):
            st.code(s["extrait"], language="python")
            if projet:
                st.markdown(
                    f'<a href="{lien_vscode(projet, s)}">Ouvrir dans VS Code</a>',
                    unsafe_allow_html=True,
                )


st.set_page_config(page_title="CodeLocate AI", page_icon="🔎", layout="wide")
st.title("🔎 CodeLocate AI")
st.caption("L'assistant de code 100 % local qui cite ses sources.")

if "messages" not in st.session_state:
    st.session_state.messages = []  # historique affiché : rôle, texte, sources
    st.session_state.session_id = None  # identifiant de conversation donné par l'API

# ----- Barre latérale : état du service et indexation -----
with st.sidebar:
    st.header("Projet")
    sante, erreur = appeler_api("/sante", delai=10)
    projet = None
    if erreur:
        st.error(erreur)
    else:
        st.write("Ollama :", "✅ en marche" if sante["ollama"] else "❌ arrêté")
        projet = sante["projet_indexe"]
        if projet:
            st.success(f"Projet indexé : **{Path(projet).name}** ({sante['morceaux']} morceaux)")
        else:
            st.warning("Aucun projet indexé.")

    dossier = st.text_input("Dossier du projet à indexer", value=projet or "")
    if st.button("Indexer ce projet", use_container_width=True):
        with st.spinner("Indexation en cours (environ une minute)..."):
            resultat, erreur = appeler_api("/indexer", {"dossier": dossier})
        if erreur:
            st.error(erreur)
        else:
            st.success(f"{resultat['morceaux']} morceaux indexés en {resultat['duree']} s")
            st.session_state.messages, st.session_state.session_id = [], None
            st.rerun()

    st.divider()
    if st.button("Nouvelle conversation", use_container_width=True):
        st.session_state.messages, st.session_state.session_id = [], None
        st.rerun()

# ----- Conversation -----
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("comprise"):
            st.caption(f"Question comprise comme : {message['comprise']}")
        st.markdown(message["texte"])
        afficher_sources(message.get("sources", []), projet)
        if message.get("duree"):
            st.caption(f"Répondu en {message['duree']} s")

question = st.chat_input("Pose une question sur le code, par exemple : que fait la fonction calculer_penalite ?")
if question:
    st.session_state.messages.append({"role": "user", "texte": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("CodeLocate AI cherche dans le code..."):
            resultat, erreur = appeler_api(
                "/question", {"question": question, "session_id": st.session_state.session_id}
            )
        if erreur:
            st.error(erreur)
        else:
            st.session_state.session_id = resultat["session_id"]
            comprise = resultat["question_comprise"] if resultat["question_comprise"] != question else None
            message = {
                "role": "assistant",
                "texte": resultat["reponse"],
                "sources": resultat["sources"],
                "comprise": comprise,
                "duree": resultat["duree"],
            }
            st.session_state.messages.append(message)
            if comprise:
                st.caption(f"Question comprise comme : {comprise}")
            st.markdown(resultat["reponse"])
            afficher_sources(resultat["sources"], projet)
            st.caption(f"Répondu en {resultat['duree']} s")