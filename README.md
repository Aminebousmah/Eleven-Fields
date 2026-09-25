# ElevenField · 11-Fields

> Dashboard Streamlit d'analyse football pour les **Big 5 européens** — Premier League, La Liga, Bundesliga, Serie A, Ligue 1.
> Indice de performance par profil sur **/100**, similarité statistique en **% de compatibilité**, watchlist personnelle, rapports de match notés sur 10, isolation domicile/extérieur, évolution multi-saisons.

UI 100% en français · Code en anglais · Inspiré [Data'Scout](https://datascout.pro/).

---

## Aperçu

ElevenField est un outil d'aide à la décision pour analyser et scouter des joueurs / clubs sur les 5 dernières saisons des grands championnats européens (2021-22 → 2025-26).

Il repose sur **deux sources de données** :
- **FBref** (via [`soccerdata`](https://soccerdata.readthedocs.io)) — stats équipe et joueur, saison et match-level
- **Transfermarkt** (via le [dataset Kaggle `davidcariboo/player-scores`](https://www.kaggle.com/datasets/davidcariboo/player-scores)) — photos joueurs, logos clubs, valeurs marchandes

Pas de scraping côté Transfermarkt : on consomme un dataset déjà publié, mis à jour chaque semaine.

---

## Fonctionnalités

> ⚠️ **Section à reprendre — écarts connus au 25 septembre 2026.** Le dashboard « Analyse Match »
> décrit ci-dessous a été supprimé, et `config.py` définit 29 profils de poste, pas 28. La
> navigation compte aujourd'hui 7 onglets avec une bascule Joueurs/Clubs, pas 9 dashboards.
> L'arbre à jour des fonctionnalités vit dans [`atlas.md`](atlas.md).

### 9 dashboards

| Dashboard | Description |
|---|---|
| **Accueil** | Présentation, KPIs globaux, modules disponibles |
| **Base de données** | Classements live, leaderboards top buteurs/passeurs/xG/KP/tacles, explorateur joueurs avec filtres avancés |
| **Tendances** | Sur/sous-performeurs xG, jeunes talents (U21), styles atypiques, évolution inter-saisons |
| **Vue Équipe** | Radars contextualisés (focus + médiane + top/pire 10%), indices composites, clustering KMeans+PCA, équipes similaires |
| **Profil Joueur** | **Indice Data'Scout par profil /100**, radar position, percentiles, joueurs similaires (% de compatibilité), évolution multi-saisons, vs ma shortlist, export rapport |
| **Analyse Match** | Calendrier, forme, xG vs xGA, **isolation domicile/extérieur**, **rapports de match joueur** (note /10 + 3 meilleures / 3 pires perfs) |
| **Comparaison** | Scatter ligue (xG/xGA), duel radar 2 joueurs, **shortlist personnelle**, SHAP, prédiction PPM (XGBoost) |
| **Composition** | Crée ton XI sur 7 formations (4-3-3, 4-4-2, 4-2-3-1, 3-5-2, 3-4-3, 5-3-2, 4-5-1) + 7 remplaçants, terrain visuel, KPIs cumulés |
| **Couverture** | Matrice saison × type de fichier, taille MB, lignes, état d'extraction |

### Fonctionnalités phares (inspirées Data'Scout)

- **28 profils de poste** : GK Classique/Releveur/Libéro/Réflexes · DC Stoppeur/Relanceur/Athlétique/Couverture/Moderne · Latéral Déf/Off/Wingback/Inversé · MF Sentinelle/Récupérateur/Régulateur/Box-to-Box/Relayeur/Mezzala/Meneur · Ailier Percutant/Créateur/Inversé · AC Pivot/Mobile · Buteur Pur · Faux 9 · Second Attaquant. Chaque profil a sa pondération de métriques et son score sur 100.
- **Profil dominant détecté automatiquement** par joueur, avec tagline.
- **Similarité en % de compatibilité** (au lieu d'une distance brute) pour les joueurs et les clubs.
- **Stats automatiquement ramenées à /90 minutes** dans le calcul de l'indice.
- **Filtre par défaut ≥ 1000 minutes** pour le pool de référence.
- **Watchlist personnelle** persistée en session (ajoutable depuis Profil Joueur, comparable depuis Comparaison).
- **Rapport de match noté /10** (5 + 1.5 × z-score, clippé) basé sur 16 actions positives (Gls, Ast, xG, KP, Tkl, Int…) et 7 négatives (CrdR, CrdY, Fls, Err…).
- **Top 3 / Bottom 3 matchs** identifiés automatiquement.
- **Isolation contextuelle** domicile / extérieur sur l'équipe et le joueur.
- **Évolution multi-saisons** des scores de profil pour un même joueur.
- **Photos joueurs et logos clubs** affichés partout via Transfermarkt + matching `rapidfuzz` avec table d'alias FBref → TM (~70 entrées pour gérer "Bayern Munich" → "Bayern München", "Paris S-G" → "Paris Saint-Germain", etc.).

---

## Stack technique

- **Python 3.12+**
- **Streamlit** ≥ 1.32 — frontend dashboard
- **Pandas 2.3** + **NumPy 2.4** — manipulation données
- **Plotly** — graphes interactifs (radars, scatters, gauges, terrain)
- **scikit-learn** ≥ 1.4 — KMeans, PCA, StandardScaler
- **scipy** ≥ 1.12 — `percentileofscore`
- **soccerdata == 1.8.8** ⚠️ **version verrouillée** (la 1.9.x supprime `passing`, `defense`, `possession`, `passing_types`, `goal_shot_creation`, `keeper_adv` et `read_shot_events`)
- **rapidfuzz** ≥ 3.6 — matching fuzzy FBref ↔ Transfermarkt
- **Unidecode** — normalisation accents
- **kaggle** — téléchargement du dataset Transfermarkt (optionnel)
- **xgboost** + **shap** — *lazy import* dans `comparison.py` (optionnels, commentés dans `requirements.txt`)

---

## Installation

```powershell
# 1. Cloner
git clone https://github.com/Aminebousmah/11-Fields.git
cd 11-Fields

# 2. Environnement virtuel (Python 3.12+)
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
# source .venv/bin/activate   # Linux / macOS

# 3. Dépendances
pip install -r requirements.txt
```

Sur PowerShell, si l'activation échoue (ExecutionPolicy) :
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## Lancer l'application

```powershell
streamlit run app.py
```

L'app s'ouvre sur `http://localhost:8501`.

> **Note** : au premier lancement, l'app sera vide tant qu'aucun dossier `XXYY/` (saison) n'est présent à la racine. Voir la section **Données** ci-dessous.

---

## Données

### Structure attendue

```
ElevenField/
├── 2122/                       # Saison 2021-22
│   ├── FB_team_season_stats_standard.csv
│   ├── FB_team_season_stats_keeper.csv
│   ├── ...
│   ├── FB_player_season_stats_standard.csv
│   ├── ...
│   ├── FB_team_match_stats_schedule.csv
│   ├── FB_player_match_stats_summary.csv
│   ├── FB_schedule.csv
│   ├── FB_shot_events.csv
│   ├── FB_lineups.csv
│   └── FB_events.csv
├── 2223/   …même structure…
├── 2324/   …
├── 2425/   …
├── 2526/   …
└── transfermarkt_data/         # Dataset Kaggle
    ├── players.csv
    ├── clubs.csv
    ├── competitions.csv
    └── …
```

Chaque saison fait environ **150-300 MB** de CSV (raison pour laquelle ils sont **gitignored**).

### Extraction FBref (recommandée)

Ouvrir le notebook `DataBaseHome.ipynb` et lancer dans l'ordre :
- **Cellule de configuration** — vérifie `soccerdata == 1.8.x`, définit les saisons et stat_types
- **Phase 1** — stats saison (équipe + joueur), 11 stat_types par catégorie, ~10-15 min/saison via la vue `'Big 5 European Leagues Combined'` (1 requête au lieu de 5)
- **Phase 2** — stats par match (schedule, summary, passing, defense, etc.), beaucoup plus long (plusieurs heures par saison)
- **Cellule de couverture** — matrice colorée présent/absent par saison × stat_type

Le pipeline est **idempotent** : les fichiers déjà écrits sont skippés (sauf `FORCE = True`), le cache `soccerdata` HTML est conservé, et un retry exponentiel absorbe les 403/429 de FBref.

Alternative CLI (une saison à la fois) :
```powershell
python -m data.scraper --season 2526
```

### Téléchargement dataset Transfermarkt

```powershell
# 1. Récupérer un token Kaggle (https://www.kaggle.com/settings/account → "Create New Token")
[Environment]::SetEnvironmentVariable('KAGGLE_API_TOKEN', 'KGAT_xxx', 'User')

# 2. Ouvrir un nouveau terminal et lancer
python -m transfermarkt.scraper
```

Le dataset (~150 MB unzippé) atterrit dans `transfermarkt_data/`. L'app continue de fonctionner sans (fallback gracieux) — seuls les photos/logos/valeurs marchandes ne s'afficheront pas.

### État de couverture (mai 2026)

| Saison | Team season (11) | Player season (11) | Team match (9) | Player match (7) | Schedule | Shot events |
|---|---|---|---|---|---|---|
| **2021-22** | 5 ⚠️ | 5 ⚠️ | 0 ❌ | 2 ⚠️ | ✅ | ❌ |
| **2022-23** | 5 ⚠️ | 5 ⚠️ | 0 ❌ | 2 ⚠️ | ✅ | ❌ |
| **2023-24** | 5 ⚠️ | 5 ⚠️ | 0 ❌ | 0 ❌ | ✅ | ❌ |
| **2024-25** | 11 ✅ | 11 ✅ | 9 ✅ | 7 ✅ | ✅ | ✅ |
| **2025-26** | 5 ⚠️ | 5 ⚠️ | 0 ❌ | 2 ⚠️ | ✅ | ❌ |

Seule la saison **2024-25** est complète. Compléter les 4 autres est la priorité d'extraction (voir `plan.md`). Le dashboard **Couverture** dans l'app affiche cette matrice à jour.

---

## Architecture

```
app.py                      Routeur Streamlit, sidebar, navigation
config.py                   SEASONS, LEAGUES, métriques par poste, 16 PLAYER_PROFILES, glossaire, thème, DISCLAIMER
assets/style.css            Thème sombre custom

data/
  loader.py                 SEUL endroit où on fait pd.read_csv (cache st.cache_data)
  processor.py              Logique pure pandas/numpy — radars, percentiles, clustering, similarité, profils, notes match, splits
  scraper.py                CLI : python -m data.scraper --season XXYY

components/
  charts.py                 Factories Plotly (make_radar, make_multi_radar, make_labeled_percentile_bars, …)
  filters.py                Sélecteurs globaux (saison/ligue) + contextuels (équipe/joueur)
  kpi_cards.py              KPI HTML + section header
  glossary.py               Expander définitions sigles + render_disclaimer + watchlist (session_state)

dashboards/                 9 vues, toutes via render(season, league)
  home / database / trends / team_overview / player_profile
  match_analysis / comparison / lineup_builder / coverage

transfermarkt/              Module optionnel — fallback gracieux si dataset absent
  loader.py                 Lecture CSVs Kaggle, filtre Big 5 D1 par competition_id
  matcher.py                Match fuzzy FBref ↔ TM (rapidfuzz, accent-insensitive, alias FBref→TM, fallback fuzzy seuil 78)
  scraper.py                Téléchargement Kaggle

XXYY/                       Un dossier par saison (gitignored)
transfermarkt_data/         CSVs Kaggle (gitignored)
DataBaseHome.ipynb          Pipeline d'extraction FBref (notebook autoritaire)
```

### Conventions

- **`data/loader.py` est le seul fichier qui lit des CSV.** Tout dashboard passe par `load_team_season_stats(stat_type, [season])`.
- **`data/processor.py` est pur** : pandas/numpy uniquement, jamais d'`st.*`.
- **Dashboards** : signature `render(season: str, league: str)`. Imports `from dashboards.X import render` *dans le routeur* (`app.py`), pas en haut de fichier.
- **Filtres globaux** (saison/ligue) en sidebar. **Filtres contextuels** (équipe/joueur) en haut de chaque dashboard.
- **`league == "Toutes les ligues"`** = pas de filtre ligue.
- **Cache** : tous les loaders sont `@st.cache_data(show_spinner=False)`.
- **Couleurs/thème** : passer par `config.COLORS` et `config.PLOTLY_LAYOUT`, jamais de hex hardcodé.
- **Code en anglais** (fonctions, variables, clés). **UI en français** (labels, glossaire).
- **Fallback Transfermarkt** : tous les imports TM sont entourés de `try/except` avec lambdas no-op.

---

## Choix d'implémentation notables

### Indice de performance par profil

```python
# Pour chaque profil compatible avec le poste du joueur :
score = Σ (percentile_metric × weight) / Σ weight     # parmi pool ≥ 1000 min même position

# Profil dominant = max(scores)
```

Les **stats cumulatives** (Gls, Ast, xG, Tkl…) sont automatiquement ramenées à `/90` ; les **taux** (Cmp%, Save%, SoT%, etc.) sont laissés tels quels via la liste `_RATE_STATS` dans `processor.py`.

### Similarité en % de compatibilité

```python
compat_pct = 100 / (1 + distance / scale)
```

Avec `scale=6` pour les équipes (18 features de style), `scale=4.5` pour les joueurs (8-10 métriques de poste). Distance euclidienne sur features standardisées (`StandardScaler`).

### Note de match /10

```python
pos_actions = Σ (stat × poids_positif)   # 16 stats : Gls×4, Ast×3, xG×2, KP×0.5, Tkl×0.3, …
neg_actions = Σ (stat × poids_négatif)   # 7 stats  : CrdR×5, OG×4, Err×3, CrdY×1, …
note = clip(5 + 1.5 × z_score(pos − neg), 0, 10)
```

Standardisée sur la saison du joueur, donc une note de 7 signifie "performance bien au-dessus de sa moyenne sur cette saison".

### Matching FBref ↔ Transfermarkt

Trois passes :
1. **Normalisation aggressive** : minuscules, retrait accents, apostrophes, tirets, points, espaces multiples
2. **Table d'alias FBref → TM** (~70 entrées dans `transfermarkt/matcher.py`) pour les mismatches notoires (Bayern Munich, Paris S-G, Inter Mailand, Olympique Lyon, etc.)
3. **Fallback rapidfuzz** (seuil 78) avec cache pour les cas restants

---

## Roadmap

Voir [`plan.md`](plan.md) pour le plan complet. Phases résiduelles :
- **Phase 1 — données** : compléter 4 saisons sur 5 (FBref rate-limit en cours)
- **Phase 3 — robustesse** : refactor sélecteur target_season, dédup `_numeric()`, bouton clear cache
- **Phase 4 — ML** : finir SHAP / Prédiction PPM (sortir du prototype)
- **Phase 5 — UX** : split `components/charts.py` (677 lignes), exports PNG/CSV, permaliens

---

## Disclaimer

> La data fournit des indications précieuses mais ne capte pas tout. Le leadership, l'orientation du corps, l'intelligence tactique ou les consignes de l'entraîneur ne sont pas quantifiables ici. L'analyse data doit être complétée par une analyse vidéo. Statistiques pondérées par 90 minutes (filtre par défaut : ≥ 1000 min).

---

## Documentation projet

- [`CLAUDE.md`](CLAUDE.md) — guide de contribution, conventions, pièges à éviter
- [`plan.md`](plan.md) — plan de développement, phases, critères de validation
- [`DataBaseHome.ipynb`](DataBaseHome.ipynb) — pipeline d'extraction FBref (notebook autoritaire)

---

## Licence

Pas de licence définie pour le moment. Repo personnel — toute utilisation requiert l'accord de l'auteur.

## Auteur

[Amine Bousmah](https://github.com/Aminebousmah)
