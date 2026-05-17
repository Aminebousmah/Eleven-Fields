"""
ElevenField – Configuration centrale.
Pour ajouter une saison : déposer le dossier XXYY/ avec les CSVs FBref et ajouter
l'entrée dans SEASONS.
"""
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Saisons disponibles ─────────────────────────────────────────────────────
# key = nom du dossier, value = label affiché
_ALL_SEASONS: dict[str, str] = {
    "2122": "2021-22",
    "2223": "2022-23",
    "2324": "2023-24",
    "2425": "2024-25",
    "2526": "2025-26",
}


def _detect_data_dir() -> Path:
    """
    Trouve le dossier qui contient les saisons (2122/, 2425/, etc.).
    Si on lance l'app depuis un worktree git (.claude/worktrees/xxx/), les CSV
    ne sont pas là (gitignorés). On remonte alors jusqu'au projet principal.
    """
    season_keys = list(_ALL_SEASONS.keys())
    candidates = [BASE_DIR] + list(BASE_DIR.parents)[:4]
    for d in candidates:
        for k in season_keys:
            if (d / k).exists() and any((d / k).glob("FB_*.csv")):
                return d
    return BASE_DIR


DATA_DIR = _detect_data_dir()
CHART_CLUB_DIR = DATA_DIR / "Chart Club"

# Filtre auto : ne garde que les saisons dont le dossier existe (au moins un CSV).
SEASONS: dict[str, str] = {
    k: v for k, v in _ALL_SEASONS.items()
    if (DATA_DIR / k).exists() and any((DATA_DIR / k).glob("FB_*.csv"))
} or {"2425": "2024-25"}  # fallback si rien

# ── Ligues FBref ─────────────────────────────────────────────────────────────
LEAGUES = [
    "ENG-Premier League",
    "ESP-La Liga",
    "GER-Bundesliga",
    "ITA-Serie A",
    "FRA-Ligue 1",
]

LEAGUE_LABELS = {
    "ENG-Premier League": "Premier League",
    "ESP-La Liga": "La Liga",
    "GER-Bundesliga": "Bundesliga",
    "ITA-Serie A": "Serie A",
    "FRA-Ligue 1": "Ligue 1",
}

# ── Types de fichiers connus ──────────────────────────────────────────────────
TEAM_SEASON_STATS = [
    "standard", "keeper", "keeper_adv", "shooting", "passing",
    "passing_types", "goal_shot_creation", "defense", "possession",
    "playing_time", "misc",
]

PLAYER_SEASON_STATS = [
    "standard", "shooting", "passing", "passing_types",
    "goal_shot_creation", "defense", "possession",
    "playing_time", "misc", "keeper", "keeper_adv",
]

TEAM_MATCH_STATS = [
    "keeper", "shooting", "passing", "passing_types",
    "goal_shot_creation", "defense", "possession", "misc",
]

PLAYER_MATCH_STATS = [
    "summary", "keepers", "shooting", "passing", "passing_types",
    "goal_shot_creation", "defense", "possession", "misc",
]

# ── Groupes de métriques ──────────────────────────────────────────────────────
# Radar "Avec ballon" : (fichier_stat, colonne)
METRICS_WITH_BALL: dict[str, tuple[str, str]] = {
    "xG":    ("shooting",           "xG"),
    "npxG":  ("shooting",           "npxG"),
    "xAG":   ("passing",            "xAG"),
    "SCA":   ("goal_shot_creation", "SCA"),
    "GCA":   ("goal_shot_creation", "GCA"),
    "Poss":  ("standard",           "Poss"),
    "PrgP":  ("standard",           "PrgP"),
    "PrgC":  ("standard",           "PrgC"),
    "PPA":   ("passing",            "PPA"),
    "CrsPA": ("passing",            "CrsPA"),
    "KP":    ("passing",            "KP"),
    "1/3":   ("passing",            "1/3"),
}

# Radar "Sans ballon" : (fichier_stat, colonne)
METRICS_WITHOUT_BALL: dict[str, tuple[str, str]] = {
    "Tkl":   ("defense",    "Tkl"),
    "TklW":  ("defense",    "TklW"),
    "Tkl%":  ("defense",    "Tkl%"),
    "Int":   ("defense",    "Int"),
    "Blocks":("defense",    "Blocks"),
    "Clr":   ("misc",       "Clr"),
    "Recov": ("misc",       "Recov"),
    "Press": ("possession", "Press"),
    "Succ%": ("possession", "Succ%"),
    "Fls":   ("misc",       "Fls"),
    "CrdY":  ("standard",   "CrdY"),
    "Won%":  ("misc",       "Won%"),
}

# ─────────────────────────────────────────────────────────────────────────────
# Catalogue de métriques catégorisées (libellés FR pour l'UI)
# Utilisé par : sélecteur du nuage de points, types de comparaison.
# Format : { catégorie : [(libellé_fr, stat_type, col_fbref), ...] }
# ─────────────────────────────────────────────────────────────────────────────
METRIC_CATEGORIES: dict[str, list[tuple[str, str, str]]] = {
    "Finition": [
        ("Buts",                       "standard", "Gls"),
        ("Buts hors penalty",          "standard", "G-PK"),
        ("xG",                         "shooting", "xG"),
        ("npxG (xG hors penalty)",     "shooting", "npxG"),
        ("Buts - xG (surperformance)", "shooting", "G-xG"),
        ("npxG - xG",                  "shooting", "npxG-xG"),
        ("Tirs",                       "shooting", "Sh"),
        ("Tirs cadrés",                "shooting", "SoT"),
        ("Tirs cadrés (%)",            "shooting", "SoT%"),
        ("Conversion but / tir",       "shooting", "G/Sh"),
        ("Distance moy. tirs",         "shooting", "Dist"),
    ],
    "Création": [
        ("Passes décisives",                "standard",            "Ast"),
        ("xA (xAG)",                        "passing",             "xAG"),
        ("Passes D. - xA",                  "passing",             "A-xAG"),
        ("Passes clés",                     "passing",             "KP"),
        ("Actions menant à un tir (SCA)",   "goal_shot_creation",  "SCA"),
        ("Actions menant à un but (GCA)",   "goal_shot_creation",  "GCA"),
        ("Passes dans le dernier tiers",    "passing",             "1/3"),
        ("Passes vers la surface",          "passing",             "PPA"),
        ("Centres en surface",              "passing",             "CrsPA"),
        ("Passes progressives",             "standard",            "PrgP"),
    ],
    "Offensif": [
        ("Courses progressives",            "standard",   "PrgC"),
        ("Passes progr. reçues",            "standard",   "PrgR"),
        ("Touches surface adverse",         "possession", "Att Pen"),
        ("Dribbles réussis (%)",            "possession", "Succ%"),
        ("Dribbles tentés",                 "possession", "Att"),
        ("Dribbles réussis",                "possession", "Succ"),
        ("Conduites dans le dernier tiers", "possession", "1/3"),
        ("Conduites dans la surface",       "possession", "CPA"),
    ],
    "Construction": [
        ("Passes réussies",          "passing",    "Cmp"),
        ("Passes tentées",           "passing",    "Att"),
        ("Précision passes (%)",     "passing",    "Cmp%"),
        ("Touches totales",          "possession", "Touches"),
        ("Distance passes (totale)", "passing",    "TotDist"),
        ("Distance progr. passes",   "passing",    "PrgDist"),
    ],
    "Défense": [
        ("Tacles",                "defense", "Tkl"),
        ("Tacles gagnés",         "defense", "TklW"),
        ("Tacles (%)",            "defense", "Tkl%"),
        ("Interceptions",         "defense", "Int"),
        ("Tacles + interceptions","defense", "Tkl+Int"),
        ("Blocs",                 "defense", "Blocks"),
        ("Dégagements",           "misc",    "Clr"),
        ("Récupérations",         "misc",    "Recov"),
        ("Erreurs (Err)",         "defense", "Err"),
    ],
    "Aérien": [
        ("Duels aériens gagnés",       "misc", "Won"),
        ("Duels aériens perdus",       "misc", "Lost"),
        ("Duels aériens gagnés (%)",   "misc", "Won%"),
    ],
    "Physique / Discipline": [
        ("Fautes commises",      "misc",     "Fls"),
        ("Fautes subies",        "misc",     "Fld"),
        ("Cartons jaunes",       "standard", "CrdY"),
        ("Cartons rouges",       "standard", "CrdR"),
        ("Hors-jeux",            "misc",     "Off"),
        ("Penaltys provoqués",   "misc",     "PKwon"),
        ("Penaltys concédés",    "misc",     "PKcon"),
    ],
    "Temps de jeu": [
        ("Minutes jouées",      "standard",     "Min"),
        ("Matchs joués",        "standard",     "MP"),
        ("Titularisations",     "standard",     "Starts"),
        ("Minutes par match",   "playing_time", "Mn/MP"),
        ("PPM (pts par match)", "playing_time", "PPM"),
    ],
    "Gardien": [
        ("Arrêts (%)",                  "keeper",     "Save%"),
        ("Clean sheets",                "keeper",     "CS"),
        ("Buts encaissés / 90",         "keeper",     "GA90"),
        ("PSxG - GA (surperformance)",  "keeper_adv", "PSxG-GA"),
        ("PSxG / Tir cadré",            "keeper_adv", "PSxG/SoT"),
        ("Précision passes GK (%)",     "keeper_adv", "Cmp%"),
        ("Longueur moy. passes GK",     "keeper_adv", "AvgLen"),
        ("Distance moy. interventions", "keeper_adv", "AvgDist"),
        ("Sorties hors surface (#OPA)", "keeper_adv", "#OPA"),
        ("% centres stoppés",           "keeper_adv", "Stp%"),
    ],
}


# Sets de métriques pré-câblés pour le radar de comparaison (≤8 métriques).
COMPARISON_PRESETS: dict[str, list[tuple[str, str, str]]] = {
    "Attaquant": [
        ("Buts",                "standard",   "Gls"),
        ("xG",                  "shooting",   "xG"),
        ("Tirs cadrés (%)",     "shooting",   "SoT%"),
        ("Passes décisives",    "standard",   "Ast"),
        ("xA",                  "passing",    "xAG"),
        ("Dribbles réussis (%)","possession", "Succ%"),
        ("Passes progr. reçues","standard",   "PrgR"),
        ("Courses progressives","standard",   "PrgC"),
    ],
    "Défenseur": [
        ("Tacles",             "defense", "Tkl"),
        ("Tacles gagnés",      "defense", "TklW"),
        ("Interceptions",      "defense", "Int"),
        ("Blocs",              "defense", "Blocks"),
        ("Dégagements",        "misc",    "Clr"),
        ("Duels aériens (%)",  "misc",    "Won%"),
        ("Récupérations",      "misc",    "Recov"),
        ("Précision passes (%)","passing","Cmp%"),
    ],
    "Création": [
        ("Passes décisives",     "standard",           "Ast"),
        ("xA",                   "passing",            "xAG"),
        ("Passes clés",          "passing",            "KP"),
        ("SCA",                  "goal_shot_creation", "SCA"),
        ("GCA",                  "goal_shot_creation", "GCA"),
        ("Passes vers surface",  "passing",            "PPA"),
        ("Centres en surface",   "passing",            "CrsPA"),
        ("Passes progressives",  "standard",           "PrgP"),
    ],
    "Athlétique": [
        ("Courses progressives", "standard",   "PrgC"),
        ("Passes progr. reçues", "standard",   "PrgR"),
        ("Récupérations",        "misc",       "Recov"),
        ("Duels aériens (%)",    "misc",       "Won%"),
        ("Tacles",               "defense",    "Tkl"),
        ("Dribbles réussis (%)", "possession", "Succ%"),
    ],
    "Discipline": [
        ("Fautes commises", "misc",     "Fls"),
        ("Fautes subies",   "misc",     "Fld"),
        ("Cartons jaunes",  "standard", "CrdY"),
        ("Cartons rouges",  "standard", "CrdR"),
        ("Hors-jeux",       "misc",     "Off"),
    ],
    "Construction": [
        ("Précision passes (%)",      "passing",    "Cmp%"),
        ("Passes réussies",           "passing",    "Cmp"),
        ("Passes progressives",       "standard",   "PrgP"),
        ("Touches",                   "possession", "Touches"),
        ("Passes dans dernier tiers", "passing",    "1/3"),
        ("Distance progr. passes",    "passing",    "PrgDist"),
    ],
    "Gardien": [
        ("Arrêts (%)",        "keeper",     "Save%"),
        ("Clean sheets",      "keeper",     "CS"),
        ("PSxG - GA",         "keeper_adv", "PSxG-GA"),
        ("PSxG / Tir cadré",  "keeper_adv", "PSxG/SoT"),
        ("Précision passes",  "keeper_adv", "Cmp%"),
        ("Longueur moy.",     "keeper_adv", "AvgLen"),
    ],
}


# Indices composites (nom → liste de (fichier, colonne))
PERFORMANCE_INDICES: dict[str, list[tuple[str, str]]] = {
    "Créativité": [
        ("goal_shot_creation", "SCA"),
        ("goal_shot_creation", "GCA"),
        ("passing", "KP"),
        ("passing", "PPA"),
        ("passing", "CrsPA"),
    ],
    "Danger": [
        ("shooting", "xG"),
        ("shooting", "npxG"),
        ("shooting", "Sh"),
        ("shooting", "SoT"),
    ],
    "Progression": [
        ("standard",  "PrgP"),
        ("standard",  "PrgC"),
        ("passing",   "1/3"),
    ],
    "Pressing": [
        ("possession", "Press"),
        ("possession", "Succ%"),
        ("defense",    "Tkl"),
        ("defense",    "TklW"),
    ],
    "Récupération": [
        ("defense", "Int"),
        ("defense", "Blocks"),
        ("misc",    "Clr"),
        ("misc",    "Recov"),
    ],
    "Discipline": [
        ("misc", "Fls"),
        ("misc", "Fld"),
        ("standard", "CrdY"),
        ("standard", "CrdR"),
    ],
    "Possession": [
        ("standard",   "Poss"),
        ("passing",    "Cmp%"),
        ("possession", "Touches"),
    ],
}

# Métriques joueur par position — choisies pour pertinence du rôle.
# Note : les métriques où "moins = mieux" (Fls, CrdY, GA90) sont volontairement
# omises du radar pour éviter les fausses lectures.
PLAYER_METRICS_BY_POS: dict[str, list[tuple[str, str]]] = {
    # Attaquants : finition, création, progression, pressing
    "FW": [
        ("standard",           "Gls"),
        ("shooting",           "xG"),
        ("shooting",           "SoT%"),
        ("standard",           "Ast"),
        ("passing",            "xAG"),
        ("passing",            "KP"),
        ("goal_shot_creation", "SCA"),
        ("goal_shot_creation", "GCA"),
        ("standard",           "PrgC"),
        ("standard",           "PrgR"),
    ],
    # Milieux : box-to-box — création, progression, ballon, défense
    "MF": [
        ("passing",            "xAG"),
        ("passing",            "KP"),
        ("passing",            "Cmp%"),
        ("passing",            "PPA"),
        ("standard",           "PrgP"),
        ("standard",           "PrgC"),
        ("goal_shot_creation", "SCA"),
        ("defense",            "Tkl"),
        ("defense",            "Int"),
        ("misc",                "Recov"),
    ],
    # Défenseurs : duels, interceptions, dégagements, relance
    "DF": [
        ("defense",  "Tkl"),
        ("defense",  "TklW"),
        ("defense",  "Int"),
        ("defense",  "Blocks"),
        ("misc",     "Clr"),
        ("misc",     "Recov"),
        ("misc",     "Won%"),
        ("passing",  "Cmp%"),
        ("standard", "PrgP"),
        ("standard", "PrgC"),
    ],
    # Gardiens : arrêts, clean-sheets, distribution
    "GK": [
        ("keeper",     "Save%"),
        ("keeper",     "CS"),
        ("keeper_adv", "Launch%"),
        ("keeper_adv", "AvgLen"),
    ],
}

# ── Catégories de profils (ordre d'affichage dans l'UI) ──────────────────────
PROFILE_CATEGORIES: list[str] = [
    "Gardien",
    "Défenseur Central",
    "Latéral",
    "Milieu Défensif",
    "Milieu Central",
    "Milieu Offensif",
    "Ailier",
    "Attaquant",
]


# ── Positions sur le terrain (abbréviations utilisées pour le filtre visuel) ─
# Coordonnées (x, y) pour le sélecteur clickable terrain (4-3-3 base).
# x : 0 (gauche) → 100 (droite), y : 0 (but propre) → 100 (but adverse).
FIELD_POSITIONS: dict[str, dict] = {
    "G":   {"label": "Gardien",                  "pos_group": "GK", "x": 50, "y": 5},
    "DG":  {"label": "Latéral Gauche",           "pos_group": "DF", "x": 12, "y": 22},
    "DCG": {"label": "Défenseur Central Gauche", "pos_group": "DF", "x": 36, "y": 18},
    "DCD": {"label": "Défenseur Central Droit",  "pos_group": "DF", "x": 64, "y": 18},
    "DD":  {"label": "Latéral Droit",            "pos_group": "DF", "x": 88, "y": 22},
    "MDC": {"label": "Milieu Défensif",          "pos_group": "MF", "x": 50, "y": 38},
    "MC":  {"label": "Milieu Central",           "pos_group": "MF", "x": 50, "y": 52},
    "MOC": {"label": "Milieu Offensif",          "pos_group": "MF", "x": 50, "y": 65},
    "MOG": {"label": "Milieu Offensif Gauche",   "pos_group": "MF", "x": 28, "y": 65},
    "MOD": {"label": "Milieu Offensif Droit",    "pos_group": "MF", "x": 72, "y": 65},
    "AG":  {"label": "Ailier Gauche",            "pos_group": "FW", "x": 12, "y": 80},
    "AD":  {"label": "Ailier Droit",             "pos_group": "FW", "x": 88, "y": 80},
    "SA":  {"label": "Second Attaquant",         "pos_group": "FW", "x": 38, "y": 88},
    "BU":  {"label": "Buteur",                   "pos_group": "FW", "x": 50, "y": 95},
}


# ── Profils de poste (inspirés Data'Scout) ───────────────────────────────────
# Chaque profil = dict avec :
#   pos_group        : "GK"/"DF"/"MF"/"FW" (pool de comparaison des percentiles)
#   category         : catégorie d'affichage (cf. PROFILE_CATEGORIES)
#   field_positions  : positions terrain compatibles (cf. FIELD_POSITIONS)
#   tagline          : description courte
#   metrics          : liste de (stat_type, col, poids)
#                      Poids négatif = on inverse le percentile (ex. fautes).

PLAYER_PROFILES: dict[str, dict] = {
    # ════════════════════════════════════════════════════════════════════════════
    # GARDIEN  (3)
    # ════════════════════════════════════════════════════════════════════════════
    "Gardien Classique": {
        "pos_group": "GK", "category": "Gardien", "field_positions": ["G"],
        "tagline":   "Sécurise sa cage, dominateur sur sa ligne.",
        "metrics": [
            ("keeper",     "Save%",    0.30),
            ("keeper",     "CS",       0.20),
            ("keeper",     "GA90",    -0.20),
            ("keeper_adv", "PSxG/SoT", 0.15),
            ("keeper_adv", "PSxG-GA",  0.15),
        ],
    },
    "Gardien Stoppeur": {
        "pos_group": "GK", "category": "Gardien", "field_positions": ["G"],
        "tagline":   "Vol plané, arrêts spectaculaires, surperforme ses xG.",
        "metrics": [
            ("keeper_adv", "PSxG-GA",  0.35),
            ("keeper_adv", "PSxG/SoT", 0.25),
            ("keeper",     "Save%",    0.25),
            ("keeper",     "GA90",    -0.15),
        ],
    },
    "Gardien Moderne": {
        "pos_group": "GK", "category": "Gardien", "field_positions": ["G"],
        "tagline":   "Sweeper-keeper, joue avec ses pieds, intervient haut.",
        "metrics": [
            ("keeper_adv", "Cmp%",    0.20),
            ("keeper_adv", "Launch%", 0.15),
            ("keeper_adv", "AvgLen",  0.15),
            ("keeper_adv", "#OPA",    0.15),
            ("keeper_adv", "AvgDist", 0.15),
            ("keeper",     "Save%",   0.20),
        ],
    },

    # ════════════════════════════════════════════════════════════════════════════
    # DÉFENSEUR CENTRAL  (4)
    # ════════════════════════════════════════════════════════════════════════════
    "Défenseur Stoppeur": {
        "pos_group": "DF", "category": "Défenseur Central",
        "field_positions": ["DCG", "DCD"],
        "tagline":   "Duel, dégagement, interception. Le mur.",
        "metrics": [
            ("defense", "Tkl",    0.18),
            ("defense", "TklW",   0.16),
            ("defense", "Int",    0.18),
            ("defense", "Blocks", 0.14),
            ("misc",    "Clr",    0.20),
            ("misc",    "Won%",   0.14),
        ],
    },
    "Défenseur Relanceur": {
        "pos_group": "DF", "category": "Défenseur Central",
        "field_positions": ["DCG", "DCD"],
        "tagline":   "Lit le jeu, casse les lignes par la passe.",
        "metrics": [
            ("passing",  "Cmp%",  0.20),
            ("passing",  "PrgP",  0.22),
            ("passing",  "1/3",   0.15),
            ("standard", "PrgC",  0.15),
            ("defense",  "Int",   0.13),
            ("misc",     "Recov", 0.15),
        ],
    },
    "Défenseur Athlétique": {
        "pos_group": "DF", "category": "Défenseur Central",
        "field_positions": ["DCG", "DCD", "DG", "DD"],
        "tagline":   "Vif, dominateur aérien, gagne ses courses.",
        "metrics": [
            ("misc",     "Won%",   0.28),
            ("defense",  "TklW",   0.16),
            ("defense",  "Tkl",    0.14),
            ("standard", "PrgC",   0.15),
            ("misc",     "Recov",  0.15),
            ("defense",  "Blocks", 0.12),
        ],
    },
    "Défenseur Moderne": {
        "pos_group": "DF", "category": "Défenseur Central",
        "field_positions": ["DCG", "DCD"],
        "tagline":   "Hybride : défend, relance, monte au pressing.",
        "metrics": [
            ("defense",  "Int",   0.13),
            ("misc",     "Clr",   0.13),
            ("passing",  "PrgP",  0.16),
            ("passing",  "1/3",   0.12),
            ("standard", "PrgC",  0.13),
            ("misc",     "Won%",  0.12),
            ("defense",  "Tkl",   0.11),
            ("misc",     "Recov", 0.10),
        ],
    },

    # ════════════════════════════════════════════════════════════════════════════
    # LATÉRAL  (3)
    # ════════════════════════════════════════════════════════════════════════════
    "Arrière Latéral": {
        "pos_group": "DF", "category": "Latéral", "field_positions": ["DG", "DD"],
        "tagline":   "Couvre son couloir, dur sur l'homme.",
        "metrics": [
            ("defense", "Tkl",    0.20),
            ("defense", "Int",    0.18),
            ("misc",    "Recov",  0.15),
            ("defense", "TklW",   0.15),
            ("misc",    "Won%",   0.12),
            ("passing", "Cmp%",   0.20),
        ],
    },
    "Latéral Offensif": {
        "pos_group": "DF", "category": "Latéral", "field_positions": ["DG", "DD"],
        "tagline":   "Multiplie les centres, attaque la ligne.",
        "metrics": [
            ("standard",           "PrgC",  0.18),
            ("standard",           "PrgP",  0.15),
            ("passing",            "CrsPA", 0.18),
            ("passing",            "PPA",   0.15),
            ("passing",            "xAG",   0.14),
            ("goal_shot_creation", "SCA",   0.20),
        ],
    },
    "Latéral Intérieur": {
        "pos_group": "DF", "category": "Latéral", "field_positions": ["DG", "DD"],
        "tagline":   "Pied inversé, rentre dans l'axe, hybride milieu.",
        "metrics": [
            ("passing",    "Cmp%",    0.20),
            ("passing",    "PrgP",    0.20),
            ("standard",   "PrgC",    0.15),
            ("passing",    "1/3",     0.13),
            ("defense",    "Int",     0.12),
            ("possession", "Touches", 0.12),
            ("misc",       "Recov",   0.08),
        ],
    },

    # ════════════════════════════════════════════════════════════════════════════
    # MILIEU DÉFENSIF  (3)
    # ════════════════════════════════════════════════════════════════════════════
    "Milieu Sentinelle": {
        "pos_group": "MF", "category": "Milieu Défensif", "field_positions": ["MDC"],
        "tagline":   "Devant la défense, équilibre du bloc.",
        "metrics": [
            ("defense", "Tkl",   0.18),
            ("defense", "Int",   0.20),
            ("misc",    "Recov", 0.20),
            ("passing", "Cmp%",  0.20),
            ("passing", "PrgP",  0.12),
            ("misc",    "Won%",  0.10),
        ],
    },
    "Milieu Récupérateur": {
        "pos_group": "MF", "category": "Milieu Défensif", "field_positions": ["MDC", "MC"],
        "tagline":   "Aspirateur à ballons, pressing intense.",
        "metrics": [
            ("defense", "Tkl",    0.22),
            ("defense", "TklW",   0.18),
            ("defense", "Int",    0.18),
            ("misc",    "Recov",  0.20),
            ("defense", "Blocks", 0.12),
            ("misc",    "Fls",   -0.10),
        ],
    },
    "Meneur de Jeu en Retrait": {
        "pos_group": "MF", "category": "Milieu Défensif", "field_positions": ["MDC", "MC"],
        "tagline":   "Métronome bas, dicte le tempo depuis la sentinelle.",
        "metrics": [
            ("passing",    "Cmp%",    0.26),
            ("passing",    "PrgP",    0.22),
            ("possession", "Touches", 0.18),
            ("passing",    "1/3",     0.14),
            ("misc",       "Recov",   0.12),
            ("defense",    "Int",     0.08),
        ],
    },

    # ════════════════════════════════════════════════════════════════════════════
    # MILIEU CENTRAL  (3)
    # ════════════════════════════════════════════════════════════════════════════
    "Milieu Box-to-Box": {
        "pos_group": "MF", "category": "Milieu Central", "field_positions": ["MC"],
        "tagline":   "D'une surface à l'autre, partout sur le terrain.",
        "metrics": [
            ("standard",           "PrgC",  0.14),
            ("standard",           "PrgP",  0.14),
            ("defense",            "Tkl",   0.14),
            ("misc",               "Recov", 0.14),
            ("passing",            "KP",    0.14),
            ("goal_shot_creation", "SCA",   0.14),
            ("standard",           "Gls",   0.08),
            ("standard",           "Ast",   0.08),
        ],
    },
    "Mezzala": {
        "pos_group": "MF", "category": "Milieu Central", "field_positions": ["MC", "MOC"],
        "tagline":   "Numéro 8 décroché, courses dans la surface.",
        "metrics": [
            ("standard",           "PrgC",  0.18),
            ("standard",           "PrgR",  0.16),
            ("passing",            "KP",    0.14),
            ("goal_shot_creation", "SCA",   0.14),
            ("standard",           "Gls",   0.12),
            ("standard",           "Ast",   0.12),
            ("shooting",           "xG",    0.14),
        ],
    },
    "Milieu Relayeur": {
        "pos_group": "MF", "category": "Milieu Central", "field_positions": ["MC", "MDC"],
        "tagline":   "Casse les lignes par la passe, lie les blocs.",
        "metrics": [
            ("passing",    "Cmp%",    0.20),
            ("passing",    "PrgP",    0.20),
            ("passing",    "1/3",     0.18),
            ("passing",    "KP",      0.14),
            ("standard",   "PrgC",    0.12),
            ("possession", "Touches", 0.16),
        ],
    },

    # ════════════════════════════════════════════════════════════════════════════
    # MILIEU OFFENSIF  (2)
    # ════════════════════════════════════════════════════════════════════════════
    "Meneur de Jeu": {
        "pos_group": "MF", "category": "Milieu Offensif", "field_positions": ["MOC"],
        "tagline":   "Décisif dans le dernier tiers, vision royale.",
        "metrics": [
            ("passing",            "xAG", 0.22),
            ("passing",            "KP",  0.20),
            ("passing",            "PPA", 0.15),
            ("goal_shot_creation", "SCA", 0.18),
            ("goal_shot_creation", "GCA", 0.15),
            ("standard",           "Ast", 0.10),
        ],
    },
    "Meneur de Jeu Excentré": {
        "pos_group": "MF", "category": "Milieu Offensif", "field_positions": ["MOG", "MOD"],
        "tagline":   "Numéro 10 décalé, crée depuis les couloirs.",
        "metrics": [
            ("passing",            "xAG",   0.20),
            ("passing",            "KP",    0.18),
            ("passing",            "CrsPA", 0.16),
            ("goal_shot_creation", "SCA",   0.16),
            ("standard",           "PrgC",  0.15),
            ("standard",           "Ast",   0.15),
        ],
    },

    # ════════════════════════════════════════════════════════════════════════════
    # AILIER  (5)
    # ════════════════════════════════════════════════════════════════════════════
    "Ailier Défensif": {
        "pos_group": "FW", "category": "Ailier", "field_positions": ["AG", "AD"],
        "tagline":   "Premier défenseur du couloir, replace.",
        "metrics": [
            ("defense", "Tkl",    0.20),
            ("misc",    "Recov",  0.18),
            ("defense", "Int",    0.15),
            ("defense", "TklW",   0.12),
            ("standard", "PrgC",  0.15),
            ("misc",    "Won%",   0.10),
            ("passing", "Cmp%",   0.10),
        ],
    },
    "Ailier Intérieur": {
        "pos_group": "FW", "category": "Ailier", "field_positions": ["AG", "AD", "MOG", "MOD"],
        "tagline":   "Crée depuis le demi-espace, sert ses attaquants.",
        "metrics": [
            ("passing",            "xAG",   0.22),
            ("passing",            "KP",    0.20),
            ("passing",            "CrsPA", 0.15),
            ("standard",           "Ast",   0.15),
            ("goal_shot_creation", "SCA",   0.15),
            ("standard",           "PrgC",  0.13),
        ],
    },
    "Ailier de Profondeur": {
        "pos_group": "FW", "category": "Ailier", "field_positions": ["AG", "AD"],
        "tagline":   "Court dans le dos, étire la défense.",
        "metrics": [
            ("standard",           "PrgR",  0.25),
            ("standard",           "PrgC",  0.18),
            ("possession",         "Succ%", 0.15),
            ("standard",           "Gls",   0.18),
            ("shooting",           "xG",    0.14),
            ("goal_shot_creation", "SCA",   0.10),
        ],
    },
    "Ailier Provocateur": {
        "pos_group": "FW", "category": "Ailier", "field_positions": ["AG", "AD"],
        "tagline":   "Élimine en 1v1, danger permanent ballon au pied.",
        "metrics": [
            ("standard",           "PrgC",  0.22),
            ("possession",         "Succ%", 0.18),
            ("standard",           "PrgR",  0.15),
            ("standard",           "Gls",   0.15),
            ("goal_shot_creation", "SCA",   0.15),
            ("goal_shot_creation", "GCA",   0.15),
        ],
    },
    "Ailier Buteur": {
        "pos_group": "FW", "category": "Ailier", "field_positions": ["AG", "AD"],
        "tagline":   "Pied inversé, rentre, conclut.",
        "metrics": [
            ("standard",           "Gls",   0.22),
            ("shooting",           "xG",    0.18),
            ("standard",           "PrgC",  0.16),
            ("shooting",           "SoT%",  0.12),
            ("possession",         "Succ%", 0.12),
            ("goal_shot_creation", "SCA",   0.10),
            ("standard",           "Ast",   0.10),
        ],
    },

    # ════════════════════════════════════════════════════════════════════════════
    # ATTAQUANT  (6)
    # ════════════════════════════════════════════════════════════════════════════
    "Faux 9": {
        "pos_group": "FW", "category": "Attaquant", "field_positions": ["BU", "SA"],
        "tagline":   "Décroche entre les lignes, déconstruit le bloc.",
        "metrics": [
            ("passing",            "KP",      0.18),
            ("passing",            "xAG",     0.16),
            ("goal_shot_creation", "SCA",     0.16),
            ("standard",           "Ast",     0.12),
            ("possession",         "Touches", 0.12),
            ("standard",           "PrgC",    0.10),
            ("standard",           "Gls",     0.08),
            ("shooting",           "xG",      0.08),
        ],
    },
    "Attaquant Pivot": {
        "pos_group": "FW", "category": "Attaquant", "field_positions": ["BU"],
        "tagline":   "Joue dos au but, fixe les défenseurs, gagne les duels.",
        "metrics": [
            ("misc",       "Won%",    0.25),
            ("standard",   "Gls",     0.20),
            ("shooting",   "xG",      0.15),
            ("passing",    "KP",      0.10),
            ("standard",   "Ast",     0.10),
            ("misc",       "Recov",   0.10),
            ("possession", "Touches", 0.10),
        ],
    },
    "Attaquant de Pressing": {
        "pos_group": "FW", "category": "Attaquant", "field_positions": ["BU", "SA"],
        "tagline":   "Première ligne du pressing, harcèle les défenseurs.",
        "metrics": [
            ("misc",       "Recov",  0.25),
            ("possession", "Press",  0.20),
            ("defense",    "Tkl",    0.15),
            ("possession", "Succ%",  0.13),
            ("misc",       "Won%",   0.10),
            ("misc",       "Fls",   -0.05),
            ("standard",   "Gls",    0.12),
        ],
    },
    "Attaquant de Profondeur": {
        "pos_group": "FW", "category": "Attaquant", "field_positions": ["BU", "SA"],
        "tagline":   "Court dans le dos de la défense, étire le bloc.",
        "metrics": [
            ("standard",           "PrgR",  0.22),
            ("shooting",           "xG",    0.18),
            ("standard",           "Gls",   0.18),
            ("possession",         "Succ%", 0.12),
            ("shooting",           "SoT%",  0.12),
            ("goal_shot_creation", "SCA",   0.10),
            ("standard",           "PrgC",  0.08),
        ],
    },
    "Renard des Surfaces": {
        "pos_group": "FW", "category": "Attaquant", "field_positions": ["BU"],
        "tagline":   "Le tueur des 16,50 m. Conclut tout, presque immobile.",
        "metrics": [
            ("standard", "Gls",  0.30),
            ("shooting", "xG",   0.25),
            ("shooting", "SoT%", 0.15),
            ("shooting", "Sh",   0.10),
            ("shooting", "G/Sh", 0.10),
            ("standard", "PrgR", 0.10),
        ],
    },
    "Attaquant Complet": {
        "pos_group": "FW", "category": "Attaquant", "field_positions": ["BU"],
        "tagline":   "Polyvalent : finit, décroche, presse, percute.",
        "metrics": [
            ("standard",           "Gls",   0.22),
            ("shooting",           "xG",    0.18),
            ("standard",           "PrgR",  0.15),
            ("standard",           "PrgC",  0.13),
            ("possession",         "Succ%", 0.12),
            ("shooting",           "SoT%",  0.10),
            ("goal_shot_creation", "SCA",   0.10),
        ],
    },
}

# ── Attributs composites (Résumé Data — style Football Manager) ──────────────
# 8 attributs synthétiques calculés à partir de plusieurs métriques pondérées.
# Score 0-100 par attribut, contextualisé par poste (filtre les joueurs du même
# pos_group avant calcul des percentiles).
#
# Affichage : grille 4×2 sur la page Profil Joueur, après le radar principal.

ATTRIBUTE_GROUPS: dict[str, dict] = {
    "AER": {
        "label":     "Aérien",
        "tooltip":   "Domination dans les airs : duels aériens gagnés.",
        "metrics": [
            ("misc", "Won%",  0.70),
            ("misc", "Won",   0.30),
        ],
    },
    "DEF": {
        "label":     "Défensif",
        "tooltip":   "Volume défensif : tacles, interceptions, dégagements, blocs.",
        "metrics": [
            ("defense", "Tkl",    0.20),
            ("defense", "TklW",   0.20),
            ("defense", "Int",    0.25),
            ("defense", "Blocks", 0.15),
            ("misc",    "Clr",    0.20),
        ],
    },
    "OFF": {
        "label":     "Offensif",
        "tooltip":   "Production offensive : buts, xG, tirs cadrés.",
        "metrics": [
            ("standard", "Gls",   0.30),
            ("shooting", "xG",    0.25),
            ("shooting", "SoT%",  0.15),
            ("shooting", "Sh",    0.15),
            ("shooting", "G/Sh",  0.15),
        ],
    },
    "CRE": {
        "label":     "Créatif",
        "tooltip":   "Création d'occasions : xAG, passes clés, GCA/SCA.",
        "metrics": [
            ("passing",            "xAG",   0.25),
            ("passing",            "KP",    0.20),
            ("passing",            "PPA",   0.15),
            ("goal_shot_creation", "SCA",   0.20),
            ("goal_shot_creation", "GCA",   0.20),
        ],
    },
    "CON": {
        "label":     "Conduite",
        "tooltip":   "Portage du ballon : conduites progressives, dribbles, touches.",
        "metrics": [
            ("standard",   "PrgC",    0.35),
            ("standard",   "PrgR",    0.20),
            ("possession", "Succ%",   0.20),
            ("possession", "Touches", 0.25),
        ],
    },
    "END": {
        "label":     "Endurance",
        "tooltip":   "Volume athlétique : récupérations, pressing, courses.",
        "metrics": [
            ("misc",       "Recov",  0.45),
            ("possession", "Press",  0.30),
            ("possession", "Succ%",  0.25),
        ],
    },
    "EXP": {
        "label":     "Expérience",
        "tooltip":   "Temps de jeu cumulé : matchs, titularisations, minutes.",
        "metrics": [
            ("standard", "Min",    0.45),
            ("standard", "MP",     0.30),
            ("standard", "Starts", 0.25),
        ],
    },
    "INT": {
        "label":     "Intelligence",
        "tooltip":   "Lecture du jeu : anticipation, précision passes, % duels.",
        "metrics": [
            ("defense",    "Int",   0.30),
            ("passing",    "Cmp%",  0.25),
            ("misc",       "Won%",  0.20),
            ("possession", "Succ%", 0.15),
            ("defense",    "Tkl%",  0.10),
        ],
    },
}

# Disclaimer (inspiré Data'Scout) — affiché en bas des dashboards d'analyse.
DISCLAIMER = (
    "La data fournit des indications précieuses mais ne capte pas tout. "
    "Le leadership, l'orientation du corps, l'intelligence tactique ou les "
    "consignes de l'entraîneur ne sont pas quantifiables ici. "
    "L'analyse data doit être complétée par une analyse vidéo. "
    "Statistiques pondérées par 90 minutes (filtre par défaut : ≥ 1000 min)."
)


# ── Thème visuel ──────────────────────────────────────────────────────────────
COLORS = {
    "bg":           "#0e1117",
    "surface":      "#1a1a2e",
    "card":         "#16213e",
    "border":       "#2d2d4e",
    "accent_green": "#00ff99",
    "accent_red":   "#ff4655",
    "accent_gold":  "#ffd700",
    "accent_blue":  "#00b4d8",
    "text":         "#ffffff",
    "text_muted":   "#8899aa",
    "grid":         "#2a2a3e",
}

TEAM_COLORS = [
    "#00ff99", "#ff4655", "#ffd700", "#00b4d8",
    "#ff9f43", "#a29bfe", "#fd79a8", "#55efc4",
]

# Clusters de styles de jeu (noms humains → index)
CLUSTER_NAMES = {
    0: "Possession",
    1: "Pressing Haut",
    2: "Jeu Direct",
    3: "Bloc Bas",
    4: "Équilibré",
    5: "Contre-attaque",
    6: "Latéralisé",
    7: "Physique",
}

# ── Glossaire des indicateurs ────────────────────────────────────────────────
# Sigle → définition courte (FR). Utilisé pour tooltips / expanders.
METRIC_DEFINITIONS: dict[str, str] = {
    # Standards
    "Gls":   "Buts marqués (hors penalties manqués).",
    "Ast":   "Passes décisives.",
    "G+A":   "Buts + passes décisives.",
    "G-PK":  "Buts hors penalties.",
    "PK":    "Penalties marqués.",
    "PKatt": "Penalties tentés.",
    "MP":    "Matchs joués.",
    "Min":   "Minutes jouées.",
    "Starts":"Titularisations.",
    "90s":   "Équivalents matchs complets (Min ÷ 90).",
    "age":   "Âge.",
    "pos":   "Position de jeu.",

    # Tirs / Expected
    "xG":    "Buts attendus : qualité cumulée des occasions.",
    "npxG":  "xG hors penalties.",
    "xAG":   "Passes attendues vers un tir : qualité de la dernière passe.",
    "xA":    "Passes décisives attendues.",
    "Sh":    "Tirs (hors penalties).",
    "SoT":   "Tirs cadrés.",
    "SoT%":  "% de tirs cadrés.",
    "G/Sh":  "Buts par tir.",
    "G/SoT": "Buts par tir cadré.",
    "Dist":  "Distance moyenne des tirs (yards).",

    # Création
    "SCA":   "Actions menant à un tir (2 dernières actions).",
    "GCA":   "Actions menant à un but.",
    "KP":    "Passes-clés (passe directe vers un tir).",
    "PPA":   "Passes dans la surface adverse.",
    "CrsPA": "Centres dans la surface adverse.",
    "1/3":   "Passes vers le tiers offensif.",

    # Possession / progression
    "Poss":  "% de possession.",
    "PrgP":  "Passes progressives (≥ 10 yards vers le but).",
    "PrgC":  "Conduites progressives (≥ 5 yards vers le but).",
    "PrgR":  "Réceptions de passes progressives.",
    "Touches":"Touches de balle.",
    "Carries":"Conduites de balle.",
    "Cmp":   "Passes réussies.",
    "Cmp%":  "% de passes réussies.",
    "Att":   "Passes tentées.",
    "TotDist":"Distance totale des passes.",
    "PrgDist":"Distance progressive des passes.",

    # Défense
    "Tkl":   "Tacles.",
    "TklW":  "Tacles gagnés (avec récupération).",
    "Tkl%":  "% de duels au sol gagnés.",
    "Int":   "Interceptions.",
    "Blocks":"Tirs/passes contrés.",
    "Clr":   "Dégagements.",
    "Recov": "Ballons récupérés.",
    "Press": "Pressings exercés.",
    "Succ%": "% de pressings réussis (récup ≤ 5s).",
    "Won%":  "% de duels aériens gagnés.",
    "Err":   "Erreurs menant à un tir adverse.",

    # Discipline
    "CrdY":  "Cartons jaunes.",
    "CrdR":  "Cartons rouges.",
    "Fls":   "Fautes commises.",
    "Fld":   "Fautes subies.",
    "Off":   "Hors-jeu.",
    "OG":    "Buts contre son camp.",

    # Gardien
    "Save%": "% d'arrêts.",
    "CS":    "Clean sheets.",
    "GA":    "Buts encaissés.",
    "GA90":  "Buts encaissés / 90 min.",
    "PSxG":  "Buts attendus post-tir (xG ajusté à la trajectoire).",
    "Launch%":"% de relances longues.",
    "AvgLen":"Longueur moyenne des relances.",

    # Match (équipe)
    "GF":    "Buts marqués.",
    "xGA":   "xG concédés.",
    "result":"Résultat (V/N/D).",
    "venue": "Domicile / Extérieur.",
}

# Définitions des indices composites
INDEX_DEFINITIONS: dict[str, str] = {
    "Créativité":   "Qualité de la création d'occasions (SCA, GCA, KP, PPA, CrsPA).",
    "Danger":       "Volume et qualité offensive (xG, npxG, Sh, SoT).",
    "Progression":  "Capacité à faire avancer le ballon (PrgP, PrgC, passes 1/3).",
    "Pressing":     "Intensité et efficacité du pressing (Press, Succ%, Tkl, TklW).",
    "Récupération": "Activité défensive (Int, Blocks, Clr, Recov).",
    "Discipline":   "Comportement (Fls, Fld, CrdY, CrdR — bas = mieux pour Fls/CrdY).",
    "Possession":   "Maîtrise du ballon (Poss, Cmp%, Touches).",
}


PLOTLY_LAYOUT = dict(
    paper_bgcolor=COLORS["bg"],
    plot_bgcolor=COLORS["surface"],
    font=dict(color=COLORS["text"], family="Inter, Arial, sans-serif", size=12),
    margin=dict(l=20, r=20, t=50, b=20),
    legend=dict(
        bgcolor=COLORS["card"],
        bordercolor=COLORS["border"],
        borderwidth=1,
        font=dict(color=COLORS["text"]),
    ),
    hoverlabel=dict(
        bgcolor=COLORS["card"],
        bordercolor=COLORS["border"],
        font=dict(color=COLORS["text"]),
    ),
)
