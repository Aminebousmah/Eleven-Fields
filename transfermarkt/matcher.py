"""
Matcher fuzzy entre noms FBref et Transfermarkt.

FBref écrit souvent les noms avec accents (« Kylian Mbappé »), Transfermarkt
de façon plus variable (« Mbappé », « Kylian Mbappe », etc.).
On utilise rapidfuzz + une normalisation accents-insensitive pour matcher.

Toutes les fonctions retournent None si le match est trop faible (< seuil)
ou si la donnée Transfermarkt n'est pas disponible — l'app reste fonctionnelle
sans le module Transfermarkt activé.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Optional

# unidecode — normalisation agressive (ø→o, ñ→n, ü→u, æ→ae…)
try:
    from unidecode import unidecode as _unidecode
    _HAS_UNIDECODE = True
except ImportError:
    _HAS_UNIDECODE = False

import pandas as pd
import streamlit as st

from transfermarkt.loader import (
    load_clubs, load_players, fbref_league_to_tm,
    load_player_valuations_for_season,
)

MATCH_THRESHOLD = 82  # score rapidfuzz pour match_player/match_club (1 à 1)
BATCH_FUZZY_THRESHOLD = 78  # plus permissif pour le fallback batch


# ── Aliases manuels FBref → Transfermarkt ────────────────────────────────────
# Forme : nom FBref normalisé → nom Transfermarkt normalisé (clé du lookup).
# Étendre quand on découvre un nouveau mismatch. Permet de matcher quand
# les noms divergent fortement (Bayern Munich vs Bayern München, etc.).
_TEAM_ALIASES_FBREF_TO_TM: dict[str, str] = {
    # Bundesliga
    "bayern munich":          "bayern munchen",
    "leverkusen":             "bayer 04 leverkusen",
    "bayer leverkusen":       "bayer 04 leverkusen",
    "dortmund":               "borussia dortmund",
    "eint frankfurt":         "eintracht frankfurt",
    "ein frankfurt":          "eintracht frankfurt",
    "gladbach":               "borussia monchengladbach",
    "m gladbach":             "borussia monchengladbach",
    "monchengladbach":        "borussia monchengladbach",
    "rb leipzig":             "rasenballsport leipzig",
    "leipzig":                "rasenballsport leipzig",
    "wolfsburg":              "vfl wolfsburg",
    "freiburg":               "sc freiburg",
    "stuttgart":              "vfb stuttgart",
    "werder bremen":          "sv werder bremen",
    "hoffenheim":             "tsg 1899 hoffenheim",
    "mainz 05":               "1 fsv mainz 05",
    "mainz":                  "1 fsv mainz 05",
    "augsburg":               "fc augsburg",
    "union berlin":           "1 fc union berlin",
    "heidenheim":             "1 fc heidenheim 1846",
    "st pauli":                "fc st pauli",
    "holstein kiel":          "holstein kiel",
    "bochum":                 "vfl bochum",
    # Premier League
    "manchester utd":         "manchester united",
    "manchester city":        "manchester city",
    "newcastle utd":          "newcastle united",
    "wolves":                 "wolverhampton wanderers",
    "nott ham forest":        "nottingham forest",
    "nottingham forest":      "nottingham forest",
    "west ham":               "west ham united",
    "brighton":               "brighton hove albion",
    "tottenham":              "tottenham hotspur",
    # Serie A
    "milan":                  "ac mailand",
    "inter":                  "inter mailand",
    "internazionale":         "inter mailand",
    "roma":                   "as rom",
    "napoli":                 "ssc neapel",
    "lazio":                  "lazio rom",
    "fiorentina":             "ac florenz",
    "juventus":               "juventus turin",
    "torino":                 "fc turin",
    "atalanta":               "atalanta bergamo",
    "verona":                 "hellas verona",
    "genoa":                  "fc genua 1893",
    "bologna":                "fc bologna",
    "monza":                  "ac monza",
    # La Liga
    "atletico madrid":        "atletico de madrid",
    "atletico de madrid":     "atletico de madrid",
    "athletic club":          "athletic bilbao",
    "ath bilbao":             "athletic bilbao",
    "real betis":             "real betis balompie",
    "betis":                  "real betis balompie",
    "celta vigo":             "celta de vigo",
    "real sociedad":          "real sociedad",
    "alaves":                 "deportivo alaves",
    "rayo vallecano":         "rayo vallecano",
    "las palmas":             "ud las palmas",
    "valladolid":             "real valladolid",
    "leganes":                "cd leganes",
    # Ligue 1
    "paris s g":              "paris saint germain",
    "paris s-g":              "paris saint germain",
    "paris sg":               "paris saint germain",
    "psg":                    "paris saint germain",
    "paris saint germain fc": "paris saint germain",
    "lyon":                   "olympique lyon",
    "olympique lyonnais":     "olympique lyon",
    "marseille":              "olympique marseille",
    "olympique de marseille": "olympique marseille",
    "rennes":                 "stade rennais fc",
    "nice":                   "ogc nizza",
    "monaco":                 "as monaco",
    "lille":                  "losc lille",
    "lens":                   "rc lens",
    "nantes":                 "fc nantes",
    "metz":                   "fc metz",
    "auxerre":                "aj auxerre",
    "le havre":               "le havre ac",
    "toulouse":               "fc toulouse",
    "brest":                  "stade brest 29",
    "reims":                  "stade reims",
    "strasbourg":             "rc strasbourg alsace",
    "angers":                 "sco angers",
    "saint etienne":          "as saint etienne",
    "montpellier":            "hsc montpellier",
}


def _normalize(s: str) -> str:
    """
    Normalisation agressive accent-insensitive :
    - unidecode si dispo (ø→o, ñ→n, ü→u, œ→oe, æ→ae, etc.)
    - fallback NFKd sinon
    - lowercase, suppression apostrophes, ponctuation → espace, collapse.
    """
    if s is None:
        return ""
    try:
        if pd.isna(s):
            return ""
    except Exception:
        pass
    raw = str(s)
    if _HAS_UNIDECODE:
        raw = _unidecode(raw)
    else:
        nfkd = unicodedata.normalize("NFKD", raw)
        raw = "".join(c for c in nfkd if not unicodedata.combining(c))
    raw = raw.lower()
    # Apostrophes (droits, courbes, dos, backtick)
    raw = re.sub(r"[‘’`´’]", "", raw)
    # Tirets, points, virgules, slashs, &, parenthèses, deux-points
    raw = re.sub(r"[\-\.\,\&/()\:]", " ", raw)
    # Collapse espaces
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def _normalize_team(s: str) -> str:
    """Comme `_normalize` puis applique la table d'alias FBref → TM."""
    norm = _normalize(s)
    return _TEAM_ALIASES_FBREF_TO_TM.get(norm, norm)


@st.cache_data(show_spinner=False)
def _player_index(league_filter: Optional[str] = None) -> pd.DataFrame:
    """Index des joueurs avec colonne normalisée pour matching rapide."""
    df = load_players()
    if df.empty:
        return df
    if league_filter:
        df = df[df["current_club_domestic_competition_id"] == league_filter]
    df = df.copy()
    df["_norm"] = df["name"].apply(_normalize)
    return df


@st.cache_data(show_spinner=False)
def _club_index(league_filter: Optional[str] = None) -> pd.DataFrame:
    df = load_clubs()
    if df.empty:
        return df
    if league_filter:
        df = df[df["domestic_competition_id"] == league_filter]
    df = df.copy()
    df["_norm"] = df["name"].apply(_normalize)
    df["_norm_pretty"] = df["pretty_name"].apply(_normalize) if "pretty_name" in df.columns else df["_norm"]
    return df


def match_player(
    fbref_name: str,
    fbref_team: Optional[str] = None,
    fbref_league: Optional[str] = None,
) -> Optional[dict]:
    """
    Retourne un dict {player_id, name, image_url, market_value_in_eur, current_club_id, ...}
    ou None si pas de correspondance fiable.
    """
    if not fbref_name:
        return None
    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        return None

    tm_league = fbref_league_to_tm(fbref_league)
    df = _player_index(tm_league)
    if df.empty:
        return None

    target = _normalize(fbref_name)
    choices = df["_norm"].tolist()

    res = process.extractOne(target, choices, scorer=fuzz.WRatio, score_cutoff=MATCH_THRESHOLD)
    if not res:
        return None
    _, score, idx = res
    return df.iloc[idx].to_dict()


def match_club(fbref_team: str, fbref_league: Optional[str] = None) -> Optional[dict]:
    if not fbref_team:
        return None
    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        return None

    tm_league = fbref_league_to_tm(fbref_league)
    df = _club_index(tm_league)
    if df.empty:
        return None

    # Utilise _normalize_team pour appliquer la table d'alias FBref→TM
    target = _normalize_team(fbref_team)
    res = process.extractOne(target, df["_norm"].tolist(), scorer=fuzz.WRatio,
                             score_cutoff=MATCH_THRESHOLD)
    if not res:
        # Tentative sur pretty_name
        res = process.extractOne(target, df["_norm_pretty"].tolist(), scorer=fuzz.WRatio,
                                 score_cutoff=MATCH_THRESHOLD)
        if not res:
            return None
    _, score, idx = res
    return df.iloc[idx].to_dict()


# ── Valeurs marchandes historiques ────────────────────────────────────────────

def get_player_value_season(
    fbref_name: str,
    season: str,
    fbref_league: Optional[str] = None,
) -> Optional[float]:
    """
    Retourne la valeur marchande du joueur à la fin de `season` (snapshot TM
    le plus proche de la fin de saison ≤ SEASON_END_DATES[season]).
    Fallback sur la valeur actuelle si aucun historique disponible.
    """
    tm = match_player(fbref_name, fbref_league=fbref_league)
    if not tm:
        return None
    player_id = tm.get("player_id")
    if player_id is None:
        return None

    try:
        snap = load_player_valuations_for_season(season)
        if not snap.empty and "player_id" in snap.columns:
            row = snap[snap["player_id"] == player_id]
            if not row.empty:
                val = pd.to_numeric(row["market_value_in_eur"].values[0], errors="coerce")
                if pd.notna(val):
                    return float(val)
    except Exception:
        pass

    # Fallback : valeur courante
    v = tm.get("market_value_in_eur")
    return float(v) if v is not None and pd.notna(v) else None


def get_squad_value_season(
    fbref_team: str,
    season: str,
    fbref_league: Optional[str] = None,
) -> Optional[float]:
    """
    Valeur d'effectif du club à la fin de `season` : somme des valeurs TM
    de tous les joueurs dont le snapshot fin-de-saison pointe vers ce club.
    Fallback sur le calcul actuel si l'historique est vide.
    """
    club = match_club(fbref_team, fbref_league)
    if not club:
        return None
    club_id = club.get("club_id")
    if club_id is None:
        return None

    try:
        snap = load_player_valuations_for_season(season)
        if not snap.empty and "current_club_id" in snap.columns:
            sub = snap[snap["current_club_id"] == club_id]
            if not sub.empty and "market_value_in_eur" in sub.columns:
                total = pd.to_numeric(sub["market_value_in_eur"], errors="coerce").sum()
                if total > 0:
                    return float(total)
    except Exception:
        pass

    # Fallback : calcul depuis players.csv (valeur courante)
    try:
        from transfermarkt.loader import load_players
        players = load_players()
        if not players.empty and "current_club_id" in players.columns:
            sub = players[players["current_club_id"] == club_id]
            if not sub.empty and "market_value_in_eur" in sub.columns:
                total = pd.to_numeric(sub["market_value_in_eur"], errors="coerce").sum()
                return float(total) if total > 0 else None
    except Exception:
        pass
    return None


# ── Historique valeur marchande joueur ───────────────────────────────────────

def get_player_value_history(
    fbref_name: str,
    fbref_league: Optional[str] = None,
) -> "pd.DataFrame":
    """
    Retourne l'historique complet des valeurs marchandes d'un joueur.
    Colonnes : date, market_value_in_eur.
    DataFrame vide si le joueur n'est pas trouvé ou si les données sont absentes.
    """
    try:
        from transfermarkt.loader import load_player_valuations
        tm = match_player(fbref_name, fbref_league=fbref_league)
        if not tm:
            return pd.DataFrame()
        player_id = tm.get("player_id")
        if player_id is None:
            return pd.DataFrame()
        all_vals = load_player_valuations(latest_only=False)
        if all_vals.empty or "player_id" not in all_vals.columns:
            return pd.DataFrame()
        pv = all_vals[all_vals["player_id"] == player_id].copy()
        pv = pv.dropna(subset=["date"])
        if "market_value_in_eur" not in pv.columns:
            return pd.DataFrame()
        pv["market_value_in_eur"] = pd.to_numeric(pv["market_value_in_eur"], errors="coerce")
        pv = pv.dropna(subset=["market_value_in_eur"])
        pv = pv.sort_values("date").reset_index(drop=True)
        return pv[["date", "market_value_in_eur"]]
    except Exception:
        return pd.DataFrame()


def get_player_career_history(
    fbref_name: str,
    fbref_league: Optional[str] = None,
) -> "pd.DataFrame":
    """
    Retourne l'historique de carrière d'un joueur depuis appearances.csv + clubs.csv.
    Colonnes : Saison, Club, Matchs, Buts, Passes D., Minutes.
    """
    try:
        from transfermarkt.loader import load_appearances, load_clubs
        tm = match_player(fbref_name, fbref_league=fbref_league)
        if not tm:
            return pd.DataFrame()
        player_id = tm.get("player_id")
        if player_id is None:
            return pd.DataFrame()
        apps = load_appearances()
        if apps.empty or "player_id" not in apps.columns:
            return pd.DataFrame()
        paps = apps[apps["player_id"] == player_id].copy()
        if paps.empty:
            return pd.DataFrame()

        # Club names
        clubs_df = load_clubs()
        club_map: dict = {}
        if not clubs_df.empty and "club_id" in clubs_df.columns and "name" in clubs_df.columns:
            club_map = clubs_df.set_index("club_id")["name"].to_dict()

        # Season year from date
        paps = paps.dropna(subset=["date"])
        paps["year"] = paps["date"].dt.year
        paps["month"] = paps["date"].dt.month
        paps["season_year"] = paps.apply(
            lambda r: r["year"] if r["month"] >= 8 else r["year"] - 1, axis=1
        )

        # Aggregate
        agg = paps.groupby(["player_club_id", "season_year"]).agg(
            games=("appearance_id", "count"),
            goals=("goals", "sum"),
            assists=("assists", "sum"),
            minutes=("minutes_played", "sum"),
        ).reset_index()

        agg["Club"] = agg["player_club_id"].map(club_map).fillna(
            agg["player_club_id"].astype(str)
        )
        agg["Saison"] = agg["season_year"].apply(
            lambda y: f"{y}/{str(y + 1)[-2:]}"
        )
        agg = agg.sort_values("season_year", ascending=False).reset_index(drop=True)
        return agg[["Saison", "Club", "games", "goals", "assists", "minutes"]].rename(
            columns={
                "games": "Matchs", "goals": "Buts",
                "assists": "Passes D.", "minutes": "Minutes",
            }
        )
    except Exception:
        return pd.DataFrame()


def get_squad_demographics(
    fbref_team: str,
    fbref_league: Optional[str] = None,
) -> "pd.DataFrame":
    """
    Retourne le DataFrame des joueurs de l'effectif avec age, nationalité,
    poste et valeur marchande. Vide si club non trouvé.
    """
    try:
        from transfermarkt.loader import load_players
        club = match_club(fbref_team, fbref_league)
        if not club:
            return pd.DataFrame()
        club_id = club.get("club_id")
        if club_id is None:
            return pd.DataFrame()
        players_df = load_players()
        if players_df.empty or "current_club_id" not in players_df.columns:
            return pd.DataFrame()
        squad = players_df[players_df["current_club_id"] == club_id].copy()
        if squad.empty:
            return pd.DataFrame()
        # Age from date_of_birth
        if "date_of_birth" in squad.columns:
            dob = pd.to_datetime(squad["date_of_birth"], errors="coerce")
            today = pd.Timestamp.now()
            squad["age"] = ((today - dob).dt.days / 365.25).apply(
                lambda x: int(x) if pd.notna(x) and x > 0 else None
            )
        if "market_value_in_eur" in squad.columns:
            squad["market_value_in_eur"] = pd.to_numeric(
                squad["market_value_in_eur"], errors="coerce"
            )
        return squad.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


# ── Helpers d'usage rapide pour l'UI ──────────────────────────────────────────

def get_player_photo(name: str, league: Optional[str] = None) -> Optional[str]:
    m = match_player(name, fbref_league=league)
    return m.get("image_url") if m else None


def get_player_value(name: str, league: Optional[str] = None) -> Optional[float]:
    m = match_player(name, fbref_league=league)
    if not m:
        return None
    v = m.get("market_value_in_eur")
    return float(v) if pd.notna(v) else None


def get_club_logo(team: str, league: Optional[str] = None) -> Optional[str]:
    m = match_club(team, league)
    return m.get("logo_url") if m else None


def format_value(value_eur: Optional[float]) -> str:
    """3500000 → '3,5 M€'. None → '—'."""
    if value_eur is None or pd.isna(value_eur):
        return "—"
    if value_eur >= 1e6:
        return f"{value_eur / 1e6:.1f} M€"
    if value_eur >= 1e3:
        return f"{value_eur / 1e3:.0f} k€"
    return f"{value_eur:.0f} €"


# ── Enrichissement batch de DataFrames ────────────────────────────────────────

def _fuzzy_resolve(target: str, choices: list[str], cache: dict,
                    threshold: int = BATCH_FUZZY_THRESHOLD) -> Optional[str]:
    """Match fuzzy d'un target dans choices, avec cache. Retourne la clé matchée ou None."""
    if not target:
        return None
    if target in cache:
        return cache[target]
    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        cache[target] = None
        return None
    res = process.extractOne(target, choices, scorer=fuzz.WRatio,
                             score_cutoff=threshold)
    cache[target] = res[0] if res else None
    return cache[target]


def enrich_with_logos(
    df: pd.DataFrame,
    team_col: str = "team",
    league: Optional[str] = None,
    out_col: str = "logo_url",
) -> pd.DataFrame:
    """
    Ajoute `out_col` au DataFrame :
    1) match exact sur nom normalisé + table d'alias FBref→TM
    2) fallback rapidfuzz (seuil 78) pour les non-matchés
    Retourne une copie. Pas d'erreur si TM absent.
    """
    if df.empty or team_col not in df.columns:
        return df
    tm = _club_index(fbref_league_to_tm(league))
    if tm.empty or "logo_url" not in tm.columns:
        return df

    out = df.copy()
    out["__norm"] = out[team_col].apply(_normalize_team)

    # Lookup principal (norm + pretty_name)
    lookup: dict[str, str] = {}
    for _, row in tm.iterrows():
        for key in [row.get("_norm"), row.get("_norm_pretty")]:
            if key and key not in lookup:
                lookup[key] = row["logo_url"]

    out[out_col] = out["__norm"].map(lookup)

    # Fuzzy fallback sur les valeurs manquantes
    missing = out[out_col].isna() & out["__norm"].astype(bool)
    if missing.any():
        choices = list(lookup.keys())
        cache: dict = {}
        for idx in out.index[missing]:
            target = out.at[idx, "__norm"]
            matched = _fuzzy_resolve(target, choices, cache)
            if matched:
                out.at[idx, out_col] = lookup[matched]

    return out.drop(columns=["__norm"])


def enrich_with_photos(
    df: pd.DataFrame,
    player_col: str = "player",
    league: Optional[str] = None,
    add_value: bool = True,
) -> pd.DataFrame:
    """
    Ajoute `image_url` (et `market_value_in_eur` si add_value).
    Match exact + fuzzy fallback (rapidfuzz seuil 78).
    """
    if df.empty or player_col not in df.columns:
        return df
    tm = _player_index(fbref_league_to_tm(league))
    if tm.empty:
        return df

    out = df.copy()
    out["__norm"] = out[player_col].apply(_normalize)

    cols = ["_norm", "image_url"]
    if add_value and "market_value_in_eur" in tm.columns:
        cols.append("market_value_in_eur")
    sub = tm[cols].drop_duplicates(subset="_norm")

    # Match exact d'abord
    out = out.merge(sub.rename(columns={"_norm": "__norm"}),
                    on="__norm", how="left")

    # Fuzzy fallback
    missing = out["image_url"].isna() & out["__norm"].astype(bool)
    if missing.any():
        choices = sub["_norm"].tolist()
        lookup_img = dict(zip(sub["_norm"], sub["image_url"]))
        lookup_val = (
            dict(zip(sub["_norm"], sub.get("market_value_in_eur", [None] * len(sub))))
            if "market_value_in_eur" in sub.columns else {}
        )
        cache: dict = {}
        for idx in out.index[missing]:
            target = out.at[idx, "__norm"]
            matched = _fuzzy_resolve(target, choices, cache)
            if matched:
                out.at[idx, "image_url"] = lookup_img.get(matched)
                if "market_value_in_eur" in out.columns and matched in lookup_val:
                    out.at[idx, "market_value_in_eur"] = lookup_val[matched]

    return out.drop(columns=["__norm"])
