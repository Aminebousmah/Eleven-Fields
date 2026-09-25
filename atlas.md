# Atlas — ElevenField

Dashboard Streamlit d'analyse football sur les cinq grands championnats européens. Il sert à comparer des joueurs et des clubs, les classer par profil tactique et repérer les écarts entre performance réelle et performance attendue. Usage personnel de scouting et d'analyse.

## Domaine · Socle applicatif
Ce qui tient l'application ensemble : la navigation, la configuration partagée et le vocabulaire visuel.

### Shell et navigation — en ligne
Routeur à sept onglets avec une bascule Joueurs/Clubs qui change la vue rendue par onglet.
- `app.py`
> Les quatre premiers onglets sont `mode_aware` : le même identifiant d'onglet route vers deux dashboards différents selon la bascule. Les imports de dashboards se font dans `_route()`, jamais en tête de fichier, pour que l'application démarre même si un module est cassé.

### Configuration métier — en ligne
Saisons, ligues, profils de poste, métriques par catégorie, presets de comparaison et définitions du glossaire.
- `config.py`
- `components/glossary.py`
> Les saisons ont deux écritures : la clé de dossier (`"2425"`) et le libellé affiché (`"2024-25"`). Tout le code manipule la clé, seule l'interface montre le libellé.

### Système de design — en ligne
Primitives HTML et CSS réutilisées par tous les dashboards : cartes, tuiles de stats, barres de percentile, jauges SVG, en-têtes de section.
- `components/design.py`
- `components/kpi_cards.py`
- `assets/elevenfield.css`
- `assets/style.css`
> Les couleurs sont définies en `oklch` dans le CSS, mais Plotly ne comprend pas cette notation : tout graphe doit recevoir des valeurs hexadécimales. `assets/style.css` est l'ancien thème, encore chargé ; `elevenfield.css` porte le système actuel.

## Domaine · Analyse joueur
Les quatre angles sous lesquels un joueur peut être regardé.

### Fiche joueur — en ligne
Page complète d'un joueur : en-tête avec photo, jauge du profil dominant, bandes de percentiles, forces et faiblesses, joueurs similaires, évolution multi-saisons.
- `dashboards/player_profile.py`
- `components/report_card.py`
> Les percentiles sont calculés contre les joueurs de même poste ayant au moins 500 minutes, pas contre toute la ligue : un défenseur n'est jamais comparé à un attaquant.

### Classement par profil tactique — en ligne
Palmarès des joueurs pour un profil donné, avec sélecteur de position sur un terrain dessiné en SVG.
- `dashboards/ranking_player.py`
> Le terrain SVG doit être construit en une seule chaîne sans indentation : quatre espaces en début de ligne font interpréter le bloc comme du code par le moteur Markdown de Streamlit, et le SVG s'affiche alors en texte brut.

### Duel joueurs — en ligne
Comparaison de deux joueurs : cartes en miroir, radar superposé, lecture rapide générée automatiquement et tableau de répartition métrique par métrique.
- `dashboards/comparison.py`
> Le mode « Auto » choisit les métriques d'après le poste du premier joueur. Une métrique n'apparaît que si les deux joueurs ont une valeur : sur une saison aux données partielles, le radar se réduit tout seul.

### Nuage joueurs — en ligne
Nuage de points à deux métriques librement choisies, avec quadrants ou clustering K-means.
- `dashboards/scatter_player.py`
> Les libellés de quadrant ne s'affichent que quand le K-means est désactivé : les deux lectures se contrediraient à l'écran.

## Domaine · Analyse club
Les mêmes angles, appliqués aux équipes.

### Fiche club — en ligne
Page d'une équipe : en-tête avec logo, six jauges d'indices composites contre la ligue, meilleurs buteurs et passeurs de l'effectif.
- `dashboards/team_overview.py`
> Les six indices supposent les statistiques FBref complètes. Sur les saisons alimentées par Understat, seuls quatre sont calculables et les deux autres restent vides.

### Classement clubs — en ligne
Palmarès des clubs sur les indices composites, avec logos et détail par indice.
- `dashboards/ranking_club.py`

### Nuage clubs — en ligne
Nuage de points des équipes sur deux métriques, avec clustering par style de jeu.
- `dashboards/scatter_club.py`

## Domaine · Tendances et veille
Ce qui remonte tout seul, sans que l'utilisateur ait à chercher.

### Sur et sous-performeurs xG — en ligne
Repère les joueurs dont le nombre de buts s'écarte le plus de leurs buts attendus, dans les deux sens.
- `dashboards/trends.py`
> Le seuil est à 600 minutes jouées : en dessous, un seul but chanceux suffit à propulser un joueur en tête du classement.

### Intelligence Médias — en ligne
Récupère des articles par flux RSS et les fait analyser par Claude Haiku : sentiment, club concerné, thème.
- `dashboards/media_intel.py`
- `media/`
> La clé API est cherchée dans trois emplacements successifs : variable d'environnement, clé plate dans `secrets.toml`, puis section `[anthropic]`. Sans clé, la section bascule sur un contenu local au lieu de planter.

## Domaine · Outils
Ce qui ne rentre ni dans joueur ni dans club.

### Constructeur de composition — en ligne
Compose un onze de départ et sept remplaçants sur sept schémas tactiques, avec terrain visuel et cumul des indicateurs.
- `dashboards/lineup_builder.py`

### Story — en cours
Épingle des cartes depuis les autres onglets et assemble un fil de texte à partir de la sélection.
- `app.py`
> Le tableau des cartes épinglées vit dans `st.session_state`, il n'est donc pas persisté : fermer l'onglet du navigateur vide la sélection. L'ordre se règle avec des boutons, Streamlit n'offrant pas de glisser-déposer natif.
> Statut déduit du code seul, sans test de l'onglet en conditions réelles : à confirmer ou à passer en ligne (voir « À trancher »).

### Couverture des données — en ligne
Matrice saison par type de fichier, pour voir d'un coup d'œil ce qui manque.
- `dashboards/coverage.py`

### Accueil et explorateur — gelée
Ancienne page d'accueil et explorateur de base de données, construits puis retirés de la navigation lors de la refonte à sept onglets. Les fichiers sont toujours suivis, mais le routeur ne les appelle plus.
- `dashboards/home.py`
- `dashboards/database.py`
- `archives/explorer_home.py.bak`
- `archives/studio.py.bak`

## Domaine · Données
D'où viennent les chiffres et ce qu'on leur fait subir.

### Chargement des CSV — en ligne
Point d'entrée unique de lecture des fichiers de saison, avec cache Streamlit et détection automatique du dossier de données.
- `data/loader.py`
> Seul fichier du projet autorisé à appeler `pd.read_csv`. La conversion numérique a une liste d'exclusion explicite : sans elle, les colonnes `result`, `team` ou `player` deviennent des valeurs manquantes.

### Calculs statistiques — en ligne
Toute la logique de calcul : percentiles, radars contextualisés, scores de profil, similarité, clustering, écarts entre buts et buts attendus.
- `data/processor.py`
> Module volontairement pur, pandas et numpy uniquement, jamais d'appel `st.*`. C'est ce qui permet de le tester ou de le réutiliser hors Streamlit.

### Graphiques — en ligne
Fabriques Plotly partagées : radars simples et superposés, nuages, barres de percentile, jauges.
- `components/charts.py`
> `config.PLOTLY_LAYOUT` contient déjà `margin` et `hoverlabel` : les repasser dans un `update_layout` lève une erreur de doublon d'argument.

### Sélecteurs et filtres — en ligne
Sélecteurs de saison, de ligue, d'équipe et de joueur, plus le garde-fou qui attend un clic avant de charger les données lourdes.
- `components/filters.py`

### Extraction FBref — gelée
Pipeline d'extraction vers les dossiers de saison : notebook de référence et équivalents en ligne de commande.
- `data/scraper.py`
- `DataBaseHome.ipynb`
- `StreamLite_11_Fields.ipynb`
- `fbref_extract.py`
- `scrape_2526.py`
> Bloqué : FBref a coupé l'accès depuis les adresses résidentielles. Le code fonctionne toujours et reste utilisable derrière un proxy, mais les saisons manquantes ont été comblées autrement. `soccerdata` est figé en 1.8.x, la 1.9 retirant la moitié des types de statistiques.

### Enrichissement Transfermarkt — en ligne
Photos de joueurs, logos de clubs, valeurs marchandes et drapeaux, rapprochés des noms FBref par correspondance floue.
- `transfermarkt/`
- `components/flags.py`
- `flags.csv`
> Les noms diffèrent entre les deux sources ; une table d'environ soixante-dix alias couvre les cas notoires avant que la correspondance floue ne prenne le relais. Tout le module est importé sous `try/except` : l'application tourne sans lui.

## Domaine · Outillage et documentation
Ce qui permet d'installer, de lancer et de comprendre le projet.

### Environnement et déploiement — en ligne
Dépendances figées, fichiers ignorés par Git, description de processus pour un hébergement de type Heroku.
- `requirements.txt`
- `.gitignore`
- `Procfile`
> `soccerdata` est épinglé à la version exacte 1.8.8, pas à une plage : c'est volontaire et documenté dans le fichier lui-même.

### Documentation du projet — en ligne
Guide de contribution, plan de développement, présentation générale et description fonctionnelle.
- `CLAUDE.md`
- `plan.md`
- `README.md`
- `atlas.md`
> Ces fichiers ne sont lus par Atlas qu'une fois commités et poussés : une mise à jour restée en local ne compte pas. `README.md` et `CLAUDE.md` portent en tête de section un avertissement sur leurs passages périmés.

### Squelettes de paquets — en ligne
Fichiers d'initialisation qui font des dossiers des modules importables.
- `components/__init__.py`
- `dashboards/__init__.py`
- `data/__init__.py`
- `media/__init__.py`
- `transfermarkt/__init__.py`

## Suivi
| Indicateur | Actuel | Cible | Avancement |
| --- | --- | --- | --- |
| Phases terminées | 1 / 7 | 7 | 14% |
| Phases en cours | 3 / 7 | — | — |
| Onglets livrés | 7 / 7 | 7 | 100% |
| Saisons avec stats joueur complètes | 4 / 7 | 7 | 57% |
| Saisons avec stats équipe | 7 / 7 | 7 | 100% |
| Fichiers suivis décrits par une fonctionnalité | 50 / 50 | 50 | 100% |
| Tests automatisés | 0 | à définir | 0% |

## Fait
- Sept onglets avec bascule Joueurs/Clubs, chacun rendant une vue différente selon le mode.
- Système de design complet porté depuis une maquette : cartes, jauges SVG, barres de percentile, heatmap de terrain, radar en quartiers.
- Vingt-neuf profils de poste répartis en huit catégories, avec un indice de performance sur cent par profil et détection du profil dominant.
- Comparaison de deux joueurs ou deux clubs avec radar superposé, lecture automatique et tableau de répartition.
- Classement par profil tactique avec sélection de position sur un terrain dessiné.
- Nuages de points à métriques libres, quadrants et clustering K-means nommé automatiquement.
- Repérage des écarts entre buts et buts attendus, dans les deux sens.
- Veille médias branchée sur Claude Haiku, avec repli local si la clé API est absente.
- Constructeur de composition sur sept schémas tactiques.
- Enrichissement Transfermarkt avec correspondance floue des noms et repli silencieux si le jeu de données est absent.
- Statistiques équipe disponibles sur sept saisons, de 2019-20 à 2025-26.
- Statistiques joueur complètes sur quatre saisons, de 2021-22 à 2024-25.
- Environnement reproductible : dépendances figées, dépôt initialisé, README détaillé.

## À faire
- Compléter les statistiques joueur de la saison en cours : cinq types de statistiques sur les onze attendus, ce qui réduit les radars de comparaison à trois métriques au lieu de dix.
- Ajouter les statistiques joueur pour 2019-20 et 2020-21, aujourd'hui limitées aux équipes.
- Adapter les six indices composites de la fiche club aux saisons où deux d'entre eux ne sont pas calculables.
- Trancher le sort de l'accueil et de l'explorateur, hors navigation depuis la refonte : les rebrancher ou les supprimer.
- Terminer les modules d'apprentissage automatique restés à l'état de prototype.
- Découper `components/charts.py`, `data/processor.py` et `dashboards/player_profile.py`, tous au-delà de sept cents lignes.
- Mettre en place des tests sur les fonctions de calcul, aujourd'hui sans aucune couverture.
- Décider d'un hébergement : le `Procfile` existe, mais rien n'est déployé.
- Verser au dépôt les deux scripts qui alimentent réellement les données aujourd'hui, aujourd'hui non suivis par Git.
- Corriger les deux écarts de description restants dans `README.md` et `CLAUDE.md` (voir « À trancher »).

## À trancher
Points relevés lors de la mise en place du suivi, le 25 septembre 2026, qu'une décision doit clore. Chacun est une incertitude assumée, pas un oubli.

- **Les deux scripts d'import ne sont pas suivis par Git.** `data/import_kaggle.py` et `data/import_understat.py` sont ce qui remplit aujourd'hui les saisons 2021-22 à 2025-26, mais ils ne sont pas dans le dépôt. Aucune fonctionnalité de cet atlas ne peut donc les citer, et la fonctionnalité « Extraction FBref » décrit un pipeline gelé au lieu de la voie réellement utilisée. À committer, puis à décrire ici comme une fonctionnalité à part entière.
- **L'état des données annoncé dans `CLAUDE.md` est périmé.** La section « État des données » y donne cinq types de statistiques pour 2021-22, 2022-23 et 2023-24, qui en ont neuf depuis l'import Kaggle. C'est le fichier lu à chaque session de travail : tant qu'il n'est pas corrigé, il induit en erreur.
- **`README.md` décrit deux choses qui n'existent plus telles quelles** : un dashboard « Analyse Match » supprimé depuis, et vingt-huit profils de poste là où `config.py` en définit vingt-neuf.
- **Le statut de Story est déduit du code, pas d'un essai.** Il est noté `en cours` parce que la sélection n'est pas persistée et que l'ordre se règle au bouton. Si l'onglet remplit son office en l'état, il passe `en ligne`.
