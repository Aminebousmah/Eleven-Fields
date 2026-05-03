# ElevenField — Plan de développement

## Objectif final

Livrer un dashboard Streamlit complet d'analyse football sur les Big 5 européens (5 saisons, stats équipe + joueur + match), avec des modules d'exploration (Database, Trends, Team, Player, Match, Compare) appuyés sur des radars contextualisés, percentiles ligue, clustering de styles et enrichissement Transfermarkt (logos, photos, valeurs marché). L'app doit être fluide, lisible (UI FR), reproductible (env figé) et alimentée par un pipeline d'extraction FBref idempotent.

---

## Phase 0 — Fondations (FAIT)

- [x] Architecture en couches (`data/loader.py` unique entrée CSV, `processor.py` pur, dashboards via `render(season, league)`)
- [x] 8 dashboards branchés dans `app.py` (Home, Database, Trends, Team, Player, Match, Compare, Coverage)
- [x] Thème sombre custom (`assets/style.css` + `config.COLORS` + `PLOTLY_LAYOUT`)
- [x] Fallback gracieux Transfermarkt (try/except + lambda no-op)
- [x] Glossaire FR des indicateurs (`config.METRIC_DEFINITIONS`, `components/glossary.py`)
- [x] Métriques par poste FW/MF/DF/GK pour radars joueur (`config.PLAYER_METRICS_BY_POS`)
- [x] Pipeline d'extraction notebook avec retry + Big 5 Combined pour stats saison
- [x] Saison 2024-25 complète (11/11 stat_types team + player, match-level, shot_events)
- [x] Downgrade soccerdata 1.8.8 verrouillé (assert dans le notebook)
- [x] `CLAUDE.md` à la racine
- [x] Module Composition (XI + 7 remplaçants, 7 formations, terrain visuel)
- [x] **Refonte Data'Scout** : 16 profils de poste fins, indice de performance /100 par profil,
      profil dominant détecté, similarité en % de compatibilité, watchlist personnelle,
      disclaimer, home refresh.
- [x] **Rapports de match joueur** (note /10, top 3 / bottom 3, courbe chronologique).
- [x] **Isolation contextuelle** Domicile/Extérieur (équipe + joueur).
- [x] **Évolution multi-saisons** d'un joueur sur ses scores de profil.
- [x] **Comparaison vs shortlist** (cible vs membres de la watchlist).
- [x] **Export rapport markdown** téléchargeable depuis Profil Joueur.
- [x] **Minutes masquées** partout sauf Profil Joueur + Comparaison joueur (tab Joueurs).

---

## Phase 1 — Compléter la couverture des données ⏳ EN COURS

**But** : avoir 5 saisons exploitables avec au moins les stats saison avancées.

### Tâches
- [ ] Lancer Phase 1 du notebook (stats saison only) sur 2122, 2223, 2324, 2526
  - via `LEAGUES_COMBINED` pour limiter le rate-limit
- [ ] Vérifier que les 11 stat_types team_season et player_season sont présents par saison
- [ ] Lancer Phase 2 (match-level) au moins sur 2324 et 2526 (priorité : récent)
- [ ] Compléter `FB_shot_events.csv` pour 2122, 2223, 2324, 2526
- [ ] Régénérer `FB_lineups.csv` / `FB_events.csv` pour 2324 et 2526

### Critères de validation
- `dashboards/coverage.py` affiche ≥ 90 % de fichiers présents pour chaque saison
- Les radars équipe/joueur sur 2122 et 2223 ne renvoient plus "Métriques insuffisantes"
- L'onglet Tendances → "Évolution inter-saisons" couvre 2122 → 2526 sans trous

### Risques
- **403 Forbidden FBref** : IP rate-limitée. Mitigation : sleep 3-7s + Big 5 Combined + attente 1 h si bannissement.
- **Cache soccerdata corrompu** : si crash en cours d'écriture, re-télécharger via `FORCE=True` ciblé.
- **Saisons partielles côté FBref** (2526 en cours) : certaines métriques peuvent être encore absentes — accepter et documenter.

---

## Phase 2 — Reproductibilité & hygiène projet

**But** : que quelqu'un (ou moi dans 6 mois) puisse cloner, installer et lancer l'app en < 10 min.

### Tâches
- [ ] Créer `requirements.txt` (`pip freeze | grep -vE "^(pip|setuptools|wheel)"` filtré)
- [ ] Pinner explicitement `soccerdata==1.8.8`
- [ ] Créer `.gitignore` : `.venv/`, `__pycache__/`, `XXYY/*.csv`, `transfermarkt_data/*.csv`, `downloaded_files/`, `.kaggle/`, `*.pyc`
- [ ] `git init` + premier commit
- [ ] README.md court (3 sections : install, run, structure → renvoie à `CLAUDE.md`)
- [ ] Supprimer / déplacer le code mort : `load_us_player_stats`, `load_fm_match_stats`, `load_espn_matchsheet` si inutilisés à l'usage

### Critères de validation
- `python -m venv .venv && pip install -r requirements.txt && streamlit run app.py` démarre sans erreur
- `git status` propre après ajout d'un CSV de saison
- Aucun import cassé après nettoyage du code mort

### Risques
- Versions transitoires de `numpy 2.4` / `pandas 2.3` peuvent casser des libs anciennes (shap, xgboost) — tester l'install dans un venv neuf.

---

## Phase 3 — Robustesse data & UX

**But** : éliminer les bugs silencieux et rendre les messages d'erreur actionnables.

### Tâches
- [ ] Refactor `comparison.py` ligne 303 (sélecteur `target_season` illisible — extraire en helper)
- [ ] Dédupliquer `_numeric()` (présent dans `loader.py` et `processor.py`) → factoriser
- [ ] Ajouter un bouton "vider le cache Streamlit" dans la sidebar (`st.cache_data.clear()`)
- [ ] Quand un dashboard a `df.empty`, afficher *quelles* données manquent (stat_type + saison) plutôt qu'un `st.info` générique
- [ ] `home.py` : mettre à jour la liste des modules (8 et non 4)
- [ ] Stripper le HTML inline répétitif → composants `render_page_header(title, subtitle)` réutilisables

### Critères de validation
- Pas de double définition de `_numeric`
- Aucun message d'erreur générique "Pas de données" sans précision sur la cause
- Lighthouse / inspection : moins de 30 % de HTML inline en moins dans les dashboards

### Risques
- Refactoring HTML inline peut casser le thème — tester chaque dashboard après changement.

---

## Phase 4 — Finir les modules ML (SHAP / Prédiction PPM)

**But** : sortir du prototype et rendre ces deux features utilisables.

### Tâches
- [ ] SHAP : ajouter un sélecteur de target (xG / Pts / xGA, pas que xG)
- [ ] SHAP : afficher un beeswarm en plus du bar chart
- [ ] Prédiction PPM : valider la colonne PPM (présente dans `playing_time` ?). Sinon, calculer Pts/MP depuis schedule.
- [ ] Prédiction PPM : afficher MAE / R² sur split saisons précédentes
- [ ] Documenter les features utilisées et écartées (drop_kw)

### Critères de validation
- SHAP tourne sur les 5 saisons sans `Colonne X introuvable`
- Prédiction PPM affiche un classement plausible + métriques d'erreur

### Risques
- xgboost / shap incompatibles avec numpy 2.x sur certaines plateformes — fallback sklearn.

---

## Phase 5 — Améliorations UX ciblées

**But** : passer d'un outil "qui marche" à un outil "agréable à utiliser".

### Tâches
- [ ] Splitter `components/charts.py` (677 lignes) en `radar.py / scatter.py / bars.py / gauges.py`
- [ ] Ajouter un export PNG/CSV sur les dataframes principaux (Database, leaderboards)
- [ ] Permaliens : encoder saison/ligue/équipe/joueur dans l'URL (Streamlit query params)
- [ ] Mode "Comparer" sur Trends (overlay 2 saisons sur le scatter xG vs Buts)
- [ ] Tooltips Plotly enrichis (logos clubs, photos joueurs sur hover si TM dispo)

### Critères de validation
- Aucun fichier > 400 lignes dans `components/`
- Refresh de l'app via URL recharge l'état exact

### Risques
- Streamlit query params : API encore mouvante selon version — vérifier la version installée.

---

## Phase 6 — Tests & déploiement (optionnel)

**But** : non-régression sur les calculs critiques + rendre l'app accessible.

### Tâches
- [ ] `tests/` avec pytest sur `data/processor.py` (percentile, build_radar_with_context, find_xg_outliers)
- [ ] Fixture CSV mini (~10 équipes × 2 saisons) pour tests
- [ ] Choix déploiement : Streamlit Community Cloud (gratuit, public) vs HF Spaces vs self-host
- [ ] Si déploiement : adapter chemins data (cloud storage ou bundled CSVs allégés)

### Critères de validation
- `pytest` passe sur les 3 fonctions clés
- App accessible via URL publique (ou décision explicite de rester local)

### Risques
- Volume données (`XXYY/` total ≈ ?? MB) potentiellement trop gros pour Streamlit Cloud (1 GB limite repo). Prévoir extraction à la demande ou stockage externe.

---

## Backlog / idées futures (non priorisé)

- Module xG flow par match (scatter chronologique des shots)
- Détection automatique de styles tactiques nommés ("Klopp gegenpressing-like")
- Comparaison cross-saison pour un même joueur (évolution de carrière)
- Intégration WhoScored / Sofascore pour ratings
- API REST légère (FastAPI) pour exposer les calculs aux notebooks externes
- Dark/light theme toggle
- Mode "scout" : recommandation de joueurs similaires (k-NN sur percentiles)

---

## Légende

- [x] fait · [ ] à faire · ⏳ en cours · ❌ bloqué (cause documentée)

**Phase active : 1** (compléter la couverture des données).
**Prochaine action concrète** : relancer Phase 1 du notebook sur les 4 saisons incomplètes une fois le rate-limit FBref retombé.
