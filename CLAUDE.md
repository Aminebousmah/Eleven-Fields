# ElevenField — Guide projet

## Contexte

**ElevenField** est un dashboard Streamlit d'analyse football pour les **Big 5 européens** (Premier League, La Liga, Bundesliga, Serie A, Ligue 1).
Objectif : explorer 5 saisons (2021-22 → 2025-26) de stats équipe et joueur via radars contextualisés, percentiles ligue, clustering de styles, comparaisons et tendances. Données FBref (via `soccerdata`) enrichies avec Transfermarkt (logos, photos, valeurs marché).

UI 100 % en français, code/clés en anglais.

## Stack

- **Python 3.12+** · Streamlit · Pandas 2.3 · NumPy 2.4
- **Plotly** (graphes interactifs) · scikit-learn (KMeans/PCA) · scipy (`percentileofscore`)
- **soccerdata 1.8.8** (⚠️ version verrouillée — 1.9.x supprime des stat_types)
- **rapidfuzz** (matching FBref ↔ Transfermarkt, accent-insensitive, seuil 82)
- xgboost + shap (lazy import dans `comparison.py`)

Pas de `pyproject.toml` / `requirements.txt` à ce jour — env manuel dans `.venv/`.

## Structure

```
app.py                      Routeur Streamlit, sidebar, navigation
config.py                   SEASONS, LEAGUES, métriques par poste, glossaire, thème
assets/style.css            Thème sombre custom

data/
  loader.py                 ⭐ SEUL endroit où on fait pd.read_csv (cache st.cache_data)
  processor.py              Logique pure pandas/numpy — aucun st.* ici
  scraper.py                CLI : python -m data.scraper --season 2526

components/
  charts.py                 Factories Plotly (make_radar, make_multi_radar, …)
  filters.py                Sélecteurs globaux (saison/ligue) + contextuels (équipe/joueur)
  kpi_cards.py              KPI HTML + section header
  glossary.py               Expander définitions sigles

dashboards/                 8 vues, toutes via render(season, league)
  home / database / trends / team_overview / player_profile
  match_analysis / comparison / coverage

transfermarkt/              Module optionnel — fallback gracieux si dataset absent
  loader.py · matcher.py · scraper.py (Kaggle)

XXYY/                       Un dossier par saison (2122, 2223, 2324, 2425, 2526)
  FB_team_season_stats_*.csv, FB_player_season_stats_*.csv,
  FB_team_match_stats_*.csv, FB_player_match_stats_*.csv,
  FB_schedule.csv, FB_shot_events.csv, FB_lineups.csv, FB_events.csv

transfermarkt_data/         CSVs Kaggle (davidcariboo/player-scores)
DataBaseHome.ipynb          Pipeline d'extraction FBref (notebook autoritaire)
```

## Commandes essentielles

```powershell
# Activer l'env
.venv\Scripts\Activate.ps1

# Lancer l'app
streamlit run app.py

# Extraction FBref (option 1 — notebook, recommandé) :
#   ouvrir DataBaseHome.ipynb, exécuter cellules dans l'ordre

# Extraction FBref (option 2 — CLI, une saison) :
python -m data.scraper --season 2526

# Téléchargement dataset Transfermarkt
python -m transfermarkt.scraper      # nécessite KAGGLE_API_TOKEN
```

Pas de tests, pas de build, pas de CI configurés.

## Conventions

- **`data/loader.py` est le seul fichier qui lit des CSV.** Tout dashboard passe par `load_team_season_stats(stat_type, [season])` etc.
- **`data/processor.py` est pur** : pandas/numpy uniquement, jamais d'`st.*`.
- **Dashboards** : signature `render(season: str, league: str)`. Les imports `from dashboards.X import render` se font *dans le routeur* (`app.py`), pas en haut de fichier.
- **Filtres globaux** (saison/ligue) en sidebar via `render_global_filters()`. **Filtres contextuels** (équipe/joueur) en haut de chaque dashboard, jamais en sidebar.
- **`league == "Toutes les ligues"`** = pas de filtre ligue (convention de filtre vide).
- **Saisons** : clé = format dossier `"2425"`, label = `"2024-25"`. Mapping dans `config.SEASONS`.
- **Cache** : tous les loaders sont `@st.cache_data(show_spinner=False)`.
- **Couleurs / thème** : passer par `config.COLORS` et `config.PLOTLY_LAYOUT`, jamais de hex hardcodé en dehors de ces constantes.
- **CSVs FBref** : double en-tête (groupe / métrique). Parser via `_parse_multiheader_csv`. Schedule, lineups, events, shot_events sont en en-tête plat → `_parse_flat_csv`.
- **Code en anglais** (noms de fonctions, variables, clés). **UI en français** (labels, messages utilisateur, glossaire).
- **Fallback Transfermarkt** : tous les imports TM sont entourés de `try/except` avec fallback `lambda *a, **k: None`. L'app doit tourner sans le module.

## À ne jamais faire

- ❌ **Ne jamais upgrade `soccerdata` au-delà de 1.8.x.** La 1.9.x retire `passing`, `defense`, `possession`, `passing_types`, `goal_shot_creation`, `keeper_adv`, et `read_shot_events`. La version est asservie via `assert sd.__version__.startswith('1.8')` dans le notebook.
- ❌ Ne pas faire `pd.read_csv` en dehors de `data/loader.py` ou `transfermarkt/loader.py`.
- ❌ Ne pas appeler `st.*` depuis `data/processor.py`.
- ❌ Ne pas convertir agressivement les colonnes texte en numérique. La fonction `_numeric()` dans `loader.py` a un **skip-set explicite** (result, opponent, team, player, league, …) — ne pas la réécrire sans préserver ce set, sous peine de retransformer "W"/"D"/"L" et noms d'équipes en NaN.
- ❌ Ne pas hammer FBref : retry exponentiel + sleep 3-5s entre requêtes. Vue `'Big 5 European Leagues Combined'` pour les stats *saison* (1 req au lieu de 5) ; liste de ligues pour les stats *match* (la vue Combined n'expose pas les matchs).
- ❌ Ne pas committer le contenu de `transfermarkt_data/`, `.venv/`, `XXYY/` (gros volumes — créer un `.gitignore` adapté avant tout `git init`).
- ❌ Ne pas ajouter d'émojis ou de docs `.md` non demandés.
- ❌ Ne pas créer de pages Streamlit dans `pages/` — la navigation est custom via `app.py` (radio sidebar).

## Fichiers à consulter en priorité

| But | Fichier |
|---|---|
| Comprendre la nav et le routage | `app.py` |
| Ajouter une saison / une ligue / une métrique | `config.py` |
| Charger une nouvelle source de données | `data/loader.py` |
| Calcul radar / percentile / cluster | `data/processor.py` |
| Ajouter un type de graphique | `components/charts.py` |
| Ajouter un sélecteur | `components/filters.py` |
| Modifier l'extraction FBref | `DataBaseHome.ipynb` (autoritaire) puis `data/scraper.py` |
| Match Transfermarkt | `transfermarkt/matcher.py` |

## État des données (avril 2026)

Seule la saison **2425** est complète (11/11 stat_types team+player + match-level + shot_events). Les saisons **2122 / 2223 / 2324 / 2526** n'ont que les 5 stat_types de base (legacy 1.9.0). Compléter ces saisons est la priorité d'extraction en cours — voir `dashboards/coverage.py` pour la matrice à jour.
