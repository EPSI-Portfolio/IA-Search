# AI Search

Un outil de recherche sur **998 titres de marchés publics français** : on tape un sujet comme `déneigement` ou `rénovation d'un bâtiment`, et il renvoie les marchés qui parlent de ce sujet, les plus pertinents en premier.

Un marché public est une annonce par laquelle une mairie, un département ou un autre organisme public indique « nous avons besoin de ces travaux ou de ce service, les entreprises peuvent candidater ». Chaque titre tient sur une ligne, par exemple :

- Interventions de psychologues pour le Département de l'Hérault
- Location de deux balayeuses avec maintenance
- Travaux de réfection d'étanchéité de toiture
- Fouilles archéologiques parking Notre-Dame de Cougnes

Le jeu de données est fourni par le cours et téléchargé automatiquement par le script d'indexation.

## Que peut-on rechercher ?

Tout sujet couvert par les marchés. Exemples de questions à essayer (en français ou en anglais) :

| Sujet | Exemple de question |
|---|---|
| Construction | `rénovation d'un bâtiment` |
| Nettoyage | `nettoyage de locaux` |
| Entretien hivernal | `déneigement` |
| Archéologie | `fouilles archéologiques` |
| Toiture | `réparation d'une toiture` |
| Social | `aide aux personnes âgées` |

Une recherche classique par mots-clés ne trouve que les titres contenant exactement vos mots. Ici, `aide aux personnes âgées` peut aussi trouver des titres proches qui utilisent d'autres mots. Si un sujet n'existe pas dans les 998 titres, les résultats seront simplement peu liés.

Le pipeline fonctionne avec n'importe quel fichier texte contenant un court document par ligne. Pour chercher autre chose, seule la fonction `get_data_from_cloud()` de `index_data/main.py` est à modifier.

## Comment ça marche, en 4 étapes

1. **Transformer le texte en nombres :** chaque titre devient une liste de nombres qui capture son sens (un *embedding*).
2. **Regrouper les titres similaires :** les titres de sens proche sont placés dans le même groupe (un *cluster*). Il y a 100 clusters.
3. **Chercher uniquement dans les groupes les plus proches :** la question est aussi transformée en nombres, et seuls les 3 clusters les plus proches sont explorés, ce qui est plus rapide que de tout parcourir. Dans ces clusters, mots-clés et sens sont combinés (recherche *hybride*).
4. **Réordonner les résultats :** un modèle d'IA lit la question et chaque résultat, répond oui/non (« ce résultat est-il pertinent ? »), et les résultats sont triés selon sa confiance (le *rerank*).

## Architecture

| Partie | Dossier | Technologie |
|---|---|---|
| Script d'indexation | `index_data/` | Python (uv), scikit-learn |
| Backend | `fastapi-backend/` | FastAPI (servi par uvicorn) |
| Front | `react-front/` | React + TypeScript (Vite), servi par nginx |
| Base de données | (image docker) | Elasticsearch 9.3.2 |
| Modèles d'IA | (image docker) | Ollama : `qwen3-embedding:0.6b` (embedding), `qwen3.5:0.8b` (rerank) |
| Orchestration | `docker-compose.yml` | Docker Compose |

**Indexation** (`index_data/main.py`) : télécharge les titres, calcule les embeddings avec Ollama, les regroupe avec K-means, puis stocke chaque cluster dans son propre index Elasticsearch (`data_0` ... `data_99`) et les 100 centres de clusters dans l'index `data_clusters`.

**Recherche** (`GET /search?q=...`) : calcule l'embedding de la question, trouve les 3 clusters les plus proches par recherche vectorielle (kNN), lance une recherche hybride (BM25 + kNN) dans ces clusters, puis réordonne les résultats avec `qwen3.5:0.8b` (score `p_yes / (p_yes + p_no)`).

## Lancer le projet

Prérequis : Docker (avec Compose), et [uv](https://docs.astral.sh/uv/) pour le script d'indexation.

**1. Démarrer la stack**
```bash
docker compose up -d --build
```
Au premier démarrage, Ollama télécharge les deux modèles (environ 2 Go) : il faut patienter quelques minutes. Pour vérifier qu'ils sont prêts :
```bash
curl http://localhost:11435/api/tags
curl http://localhost:9200
```

**2. Indexer les données** (une seule fois, une fois la stack démarrée)
```bash
cd index_data
uv run main.py
```
Le script se termine par `indexed 100 clusters`.

**3. Utiliser l'application**
- Front : http://localhost:3000
- Documentation du backend (Swagger) : http://localhost:8000/docs

## Ports

| Service | Port hôte | Remarque |
|---|---|---|
| Front | 3000 | |
| Backend | 8000 | |
| Elasticsearch | 9200 | |
| Ollama | 11435 | redirigé vers 11434 dans Docker (11434 était déjà utilisé par une installation locale d'Ollama) |

Dans le réseau Docker, le backend joint `http://elasticsearch:9200` et `http://ollama:11434` (variables d'environnement `ELASTICSEARCH_HOST` et `OLLAMA_URL`). Le script d'indexation tourne sur la machine hôte : il utilise donc `localhost:11435` et `localhost:9200` par défaut.

## Arrêter

```bash
docker compose down
```
Ne pas ajouter `-v`, sauf pour supprimer les modèles téléchargés et les données indexées.

## Remarques

- Le modèle de rerank est petit (0,8 milliard de paramètres) : il ne sépare les résultats que partiellement. Un modèle plus grand peut être choisi avec `RERANK_MODEL` dans `fastapi-backend/rerank.py`.
- Les balises `<br />` présentes dans certains titres sont supprimées avant le calcul des embeddings.
- La recherche dans les 3 clusters les plus proches est rapide, mais peut manquer un bon résultat situé dans un autre cluster.