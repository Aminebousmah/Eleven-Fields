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

import pandas as pd
import streamlit as st

from transfermarkt.loader import (
    load_clubs, load_players, fbref_league_to_tm,
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
    "paris sg":               "paris saint germain",
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
    Lowercase + retire accents + remplace apostrophes/tirets/points par espace
    + collapse les espaces multiples. Bien plus tolérant aux variations FBref/TM.
    """
    if pd.isna(s) or s is None:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in nfkd if not unicodedata.combining(c))
    s = s.lower()
    # Apostrophes (droits, courbes, dos)
    s = re.sub(r"['`’´‘]", "", s)
    # Tirets, points, virgules, slashs, &, parenthèses
    s = re.sub(r"[\-\.\,\&/()]", " ", s)
    # Collapse spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s


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

    target = _normalize(fbref_team)
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
