# CodeLocate AI

**L'assistant de code 100 % local qui cite ses sources.**

Pose des questions en français sur un projet Python : CodeLocate AI retrouve le bon code, répond en citant le fichier et les lignes, et dit « je ne sais pas » quand la réponse n'est pas dans le code. Tout tourne sur ta machine, sans connexion internet ni service payant.

> Projet en cours de construction.

## Structure

| Dossier | Rôle |
| --- | --- |
| `indexation/` | Découpage du code (ast) et création des embeddings |
| `recherche/` | Recherche par sens (ChromaDB) et par mots-clés (BM25) |
| `chatbot/` | Prompt, citations, mémoire de conversation |
| `outils/` | Statistiques calculées sur le projet |
| `api/` | Service FastAPI |
| `eval/` | Les 15 questions de référence et le script de score |