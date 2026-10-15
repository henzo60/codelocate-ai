# Questions de test (projet gestion_bibliotheque)

| N° | Question | Fichier attendu | Ce qu'elle teste |
| --- | --- | --- | --- |
| 1 | Que fait la fonction calculer_penalite ? | services/penalites.py | Nom exact présent dans le code |
| 2 | Comment est calculée l'amende quand on rend un livre trop tard ? | services/penalites.py | Recherche par le sens (« amende » absent du code) |
| 3 | Où est gérée la connexion à la base de données ? | database/connection.py | Piège des deux « connexions » |
| 4 | Que se passe-t-il quand un utilisateur se trompe plusieurs fois de mot de passe ? | auth/authentification.py | Règle cachée dans une fonction |
| 5 | Pour quelles raisons un membre peut-il se voir refuser un emprunt ? | services/emprunt_service.py | Plusieurs règles dans une fonction |