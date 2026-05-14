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

# Filtre auto : ne garde que les saisons dont le dossier existe (au moins un CSV).
SEASONS: dict[str, str] = {
    k: v for k, v in _ALL_SEASONS.items()
    if (BASE_DIR / k).exists() and any((BASE_DIR / k).glob("FB_*.csv"))
} or {"2425": "2024-25"}  # fallback si rien

# Dossiers de données
DATA_DIR = BASE_DIR           # les dossiers saison sont à la racine
CHART_CLUB_DIR = BASE_DIR / "Chart Club"

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

# ── Profils de poste (inspirés Data'Scout) ───────────────────────────────────
# Chaque profil = liste de (stat_type, col, poids).
# Poids négatif = on inverse le percentile (ex. fautes : moins = mieux).
# Un joueur reçoit un score /100 par profil compatible avec son pos_group.
# Le profil dominant = score le plus élevé.

PLAYER_PROFILES: dict[str, dict] = {
    # ── Gardiens
    "GK Classique": {
        "pos_group": "GK",
        "tagline":   "Sécurise sa cage, dominateur sur sa ligne.",
        "metrics": [
            ("keeper",     "Save%",   0.30),
            ("keeper",     "CS",      0.20),
            ("keeper",     "GA90",   -0.20),
            ("keeper_adv", "PSxG/SoT", 0.15),
            ("keeper_adv", "PSxG-GA",  0.15),
        ],
    },
    "GK Releveur": {
        "pos_group": "GK",
        "tagline":   "Premier relanceur, joue avec ses pieds.",
        "metrics": [
            ("keeper_adv", "Launch%", 0.22),
            ("keeper_adv", "AvgLen",  0.18),
            ("keeper_adv", "Cmp%",    0.20),
            ("keeper",     "Save%",   0.20),
            ("keeper_adv", "Stp%",    0.20),
        ],
    },
    # ── Défenseurs centraux
    "DC Solide": {
        "pos_group": "DF",
        "tagline":   "Duel, dégagement, interception. Le mur.",
        "metrics": [
            ("defense", "Tkl",    0.18),
            ("defense", "TklW",   0.16),
            ("defense", "Int",    0.20),
            ("defense", "Blocks", 0.14),
            ("misc",    "Clr",    0.20),
            ("misc",    "Won%",   0.12),
        ],
    },
    "DC Relanceur": {
        "pos_group": "DF",
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
    # ── Latéraux
    "Latéral Défensif": {
        "pos_group": "DF",
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
        "pos_group": "DF",
        "tagline":   "Piston moderne, multiplie les centres.",
        "metrics": [
            ("standard",           "PrgC",  0.18),
            ("standard",           "PrgP",  0.15),
            ("passing",            "CrsPA", 0.18),
            ("passing",            "PPA",   0.15),
            ("passing",            "xAG",   0.14),
            ("goal_shot_creation", "SCA",   0.20),
        ],
    },
    # ── Milieux
    "Milieu Sentinelle": {
        "pos_group": "MF",
        "tagline":   "Devant la défense, équilibre du bloc.",
        "metrics": [
            ("defense",  "Tkl",   0.18),
            ("defense",  "Int",   0.20),
            ("misc",     "Recov", 0.20),
            ("passing",  "Cmp%",  0.20),
            ("passing",  "PrgP",  0.12),
            ("misc",     "Won%",  0.10),
        ],
    },
    "Milieu Récupérateur": {
        "pos_group": "MF",
        "tagline":   "Aspirateur à ballons, pressing intense.",
        "metrics": [
            ("defense",    "Tkl",    0.22),
            ("defense",    "TklW",   0.18),
            ("defense",    "Int",    0.18),
            ("misc",       "Recov",  0.20),
            ("defense",    "Blocks", 0.12),
            ("misc",       "Fls",   -0.10),
        ],
    },
    "Milieu Box to Box": {
        "pos_group": "MF",
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
    "Milieu Relayeur": {
        "pos_group": "MF",
        "tagline":   "Métronome, fait tourner le jeu.",
        "metrics": [
            ("passing",    "Cmp%",    0.24),
            ("passing",    "PrgP",    0.20),
            ("passing",    "1/3",     0.16),
            ("passing",    "KP",      0.14),
            ("standard",   "PrgC",    0.10),
            ("possession", "Touches", 0.16),
        ],
    },
    "Meneur de Jeu": {
        "pos_group": "MF",
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
    # ── Attaquants
    "Ailier Percutant": {
        "pos_group": "FW",
        "tagline":   "Élimine en 1v1, brûle l'espace.",
        "metrics": [
            ("standard",           "PrgC",  0.22),
            ("standard",           "PrgR",  0.15),
            ("possession",         "Succ%", 0.15),
            ("standard",           "Gls",   0.18),
            ("shooting",           "xG",    0.15),
            ("goal_shot_creation", "GCA",   0.15),
        ],
    },
    "Ailier Créateur": {
        "pos_group": "FW",
        "tagline":   "Donne, centre, sert ses attaquants.",
        "metrics": [
            ("passing",            "xAG",   0.22),
            ("passing",            "KP",    0.20),
            ("passing",            "CrsPA", 0.15),
            ("standard",           "Ast",   0.15),
            ("goal_shot_creation", "SCA",   0.15),
            ("standard",           "PrgC",  0.13),
        ],
    },
    "Avant-Centre Pivot": {
        "pos_group": "FW",
        "tagline":   "Joue dos au but, fixe les défenseurs.",
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
    "Avant-Centre Mobile": {
        "pos_group": "FW",
        "tagline":   "Décroche, profondeur, polyvalent devant.",
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
    "Buteur Pur": {
        "pos_group": "FW",
        "tagline":   "Renard des surfaces, conclut tout.",
        "metrics": [
            ("standard", "Gls",  0.30),
            ("shooting", "xG",   0.25),
            ("shooting", "SoT%", 0.15),
            ("shooting", "Sh",   0.10),
            ("shooting", "G/Sh", 0.10),
            ("standard", "PrgR", 0.10),
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
