"""
Nettoyage, normalisation et calcul de métriques dérivées.
Aucun accès à st.* ici — logique pure pandas/numpy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import percentileofscore

from config import PERFORMANCE_INDICES, CLUSTER_NAMES  # noqa: F401 re-export
from data.loader import load_team_season_stats, load_player_season_stats


# ── Normalisation ─────────────────────────────────────────────────────────────

def normalize_to_max(series: pd.Series) -> pd.Series:
    """Divise par le max de la série (0–1)."""
    m = series.max()
    return series / m if m > 0 else series


def percentile_score(series: pd.Series, value: float) -> float:
    """Percentile d'une valeur dans une distribution."""
    clean = series.dropna()
    if len(clean) == 0:
        return 0.0
    return round(percentileofscore(clean, value, kind="rank"), 1)


def percentile_series(series: pd.Series) -> pd.Series:
    """Convertit chaque valeur en son percentile dans la série."""
    clean = series.dropna()
    return series.apply(
        lambda v: percentileofscore(clean, v, kind="rank") if pd.notna(v) else np.nan
    )


# ── Radar data ────────────────────────────────────────────────────────────────

def build_radar_data(
    metrics: dict[str, tuple[str, str]],
    teams: list[str],
    season: str,
    league: str | None = None,
) -> dict[str, list[float]]:
    """
    Construit les valeurs normalisées (0-1) pour un radar.

    metrics : {label: (stat_type, col)}
    teams   : liste de noms d'équipes
    Retourne : {team: [val_métrique_1, ...]}
    """
    # Cache des DFs par stat_type
    loaded: dict[str, pd.DataFrame] = {}

    result: dict[str, list[float]] = {t: [] for t in teams}

    for label, (stat_type, col) in metrics.items():
        if stat_type not in loaded:
            df = load_team_season_stats(stat_type)
            if league:
                df = df[df["league"] == league]
            df = df[df["season"] == season]
            loaded[stat_type] = df
        else:
            df = loaded[stat_type]

        if col not in df.columns:
            for t in teams:
                result[t].append(0.0)
            continue

        max_val = pd.to_numeric(df[col], errors="coerce").max()
        for team in teams:
            row = df[df["team"] == team]
            val = 0.0
            if not row.empty:
                raw = pd.to_numeric(row[col].values[0], errors="coerce")
                if pd.notna(raw) and max_val and max_val > 0:
                    val = float(raw) / float(max_val)
            result[team].append(val)

    return result


# ── Performance indices ───────────────────────────────────────────────────────

def build_performance_index(
    teams: list[str],
    season: str,
    league: str | None = None,
) -> pd.DataFrame:
    """
    Calcule les 7 indices composites (percentile moyen des métriques du groupe).
    Retourne un DataFrame [team, index_name, score].
    """
    loaded: dict[str, pd.DataFrame] = {}
    rows = []

    for idx_name, metric_list in PERFORMANCE_INDICES.items():
        # Charge les DFs nécessaires
        for stat_type, col in metric_list:
            if stat_type not in loaded:
                df = load_team_season_stats(stat_type)
                if league:
                    df = df[df["league"] == league]
                df = df[df["season"] == season]
                loaded[stat_type] = df

        for team in teams:
            scores = []
            for stat_type, col in metric_list:
                df = loaded[stat_type]
                if col not in df.columns:
                    continue
                col_series = pd.to_numeric(df[col], errors="coerce")
                team_row = df[df["team"] == team]
                if team_row.empty:
                    continue
                val = pd.to_numeric(team_row[col].values[0], errors="coerce")
                if pd.notna(val):
                    pct = percentile_score(col_series, float(val))
                    scores.append(pct)

            rows.append({
                "team": team,
                "index": idx_name,
                "score": round(np.mean(scores), 1) if scores else 0.0,
            })

    return pd.DataFrame(rows)


# ── Clustering ────────────────────────────────────────────────────────────────

CLUSTER_FEATURES = [
    ("standard",           "Poss"),
    ("shooting",           "xG"),
    ("shooting",           "npxG"),
    ("passing",            "Cmp%"),
    ("passing",            "PPA"),
    ("passing",            "KP"),
    ("standard",           "PrgP"),
    ("standard",           "PrgC"),
    ("goal_shot_creation", "SCA"),
    ("goal_shot_creation", "GCA"),
    ("defense",            "Tkl"),
    ("defense",            "TklW"),
    ("defense",            "Int"),
    ("defense",            "Blocks"),
    ("possession",         "Press"),
    ("misc",               "Recov"),
    ("misc",               "Won%"),
    ("misc",               "Fls"),
]

def build_cluster_data(season: str, league: str | None = None) -> pd.DataFrame:
    """
    Construit la matrice de features pour le clustering par style de jeu.
    Robuste aux colonnes manquantes : skippe silencieusement les features absentes.
    """
    dfs: dict[str, pd.DataFrame] = {}
    result: pd.DataFrame | None = None
    feature_cols: list[str] = []

    for stat_type, col in CLUSTER_FEATURES:
        if stat_type not in dfs:
            df = load_team_season_stats(stat_type, [season])
            if df.empty:
                continue
            if league:
                df = df[df["league"] == league]
            dfs[stat_type] = df

        df = dfs[stat_type]
        if col not in df.columns:
            continue

        sub = df[["team", "league", col]].copy()
        sub[col] = pd.to_numeric(sub[col], errors="coerce")

        if result is None:
            result = sub
        else:
            result = result.merge(sub.drop(columns=["league"]), on="team", how="left")
        feature_cols.append(col)

    if result is None or result.empty:
        return pd.DataFrame(columns=["team", "league"])

    result = result.dropna(subset=feature_cols, how="all").reset_index(drop=True)
    return result


# ── Forme équipe ──────────────────────────────────────────────────────────────

def compute_form(schedule: pd.DataFrame, team: str, n: int = 5) -> list[str]:
    """Retourne les N derniers résultats ['W','D','L'] d'une équipe."""
    df = schedule[schedule["team"] == team].copy()
    df = df.dropna(subset=["result"])
    df = df.sort_values("date", ascending=False)
    return df["result"].head(n).tolist()


# ── Radar multi-référence (focus + médiane + top10 + bottom10) ───────────────

def build_radar_with_context(
    metrics: list[tuple[str, str]] | dict[str, tuple[str, str]],
    entity_name: str,
    entity_type: str,          # "team" ou "player"
    season: str,
    league: str | None = None,
    min_minutes: int = 0,      # filtre joueurs
) -> dict[str, list]:
    """
    Construit les données d'un radar avec 4 séries : focus, médiane ligue,
    top 10% et pire 10%. Toutes normalisées 0-1 par rapport au max de la ligue.
    Utilisé pour les radars contextualisés type Football Insights.
    """
    if isinstance(metrics, dict):
        pairs = list(metrics.items())
    else:
        pairs = [(col, (stat_type, col)) for stat_type, col in metrics]

    loader = load_team_season_stats if entity_type == "team" else load_player_season_stats
    entity_col = "team" if entity_type == "team" else "player"

    labels: list[str] = []
    focus: list[float] = []
    median: list[float] = []
    top10: list[float] = []
    bottom10: list[float] = []

    # Cache DFs par stat_type pour éviter rechargements
    dfs: dict[str, pd.DataFrame] = {}

    for label, (stat_type, col) in pairs:
        if stat_type not in dfs:
            df = loader(stat_type, [season])
            if league and league != "Toutes les ligues":
                df = df[df["league"] == league]
            if entity_type == "player" and min_minutes > 0 and "Min" in df.columns:
                df = df[pd.to_numeric(df["Min"], errors="coerce") >= min_minutes]
            dfs[stat_type] = df
        df = dfs[stat_type]

        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            continue

        max_v = series.max()
        if max_v <= 0:
            continue

        row = df[df[entity_col] == entity_name]
        if row.empty:
            continue
        fv = pd.to_numeric(row[col].values[0], errors="coerce")
        if pd.isna(fv):
            continue

        labels.append(label)
        focus.append(float(fv) / float(max_v))
        median.append(float(series.median()) / float(max_v))
        top10.append(float(series.quantile(0.9)) / float(max_v))
        bottom10.append(float(series.quantile(0.1)) / float(max_v))

    return {
        "labels": labels,
        "focus": focus,
        "median": median,
        "top10": top10,
        "bottom10": bottom10,
    }


def build_percentiles_labeled(
    metrics: list[tuple[str, str]] | dict[str, tuple[str, str]],
    entity_name: str,
    entity_type: str,
    season: str,
    league: str | None = None,
    min_minutes: int = 0,
) -> list[dict]:
    """
    Retourne la liste des percentiles d'un joueur/équipe avec étiquette
    "Top X.X%" ou "Pire X.X%" (style Football Insights).
    """
    if isinstance(metrics, dict):
        pairs = list(metrics.items())
    else:
        pairs = [(col, (stat_type, col)) for stat_type, col in metrics]

    loader = load_team_season_stats if entity_type == "team" else load_player_season_stats
    entity_col = "team" if entity_type == "team" else "player"

    out: list[dict] = []
    for label, (stat_type, col) in pairs:
        df = loader(stat_type, [season])
        if league and league != "Toutes les ligues":
            df = df[df["league"] == league]
        if entity_type == "player" and min_minutes > 0 and "Min" in df.columns:
            df = df[pd.to_numeric(df["Min"], errors="coerce") >= min_minutes]
        if col not in df.columns:
            continue

        series = pd.to_numeric(df[col], errors="coerce").dropna()
        row = df[df[entity_col] == entity_name]
        if row.empty or series.empty:
            continue
        val = pd.to_numeric(row[col].values[0], errors="coerce")
        if pd.isna(val):
            continue

        pct = percentile_score(series, float(val))
        # Étiquette style FI : "Top X%" si pct >= 50, "Pire X%" sinon
        if pct >= 50:
            tag_label = f"Top {round(100 - pct, 1)}%"
            tier = "top"
        else:
            tag_label = f"Pire {round(pct, 1)}%"
            tier = "bottom"

        out.append({
            "metric": label,
            "value": float(val),
            "percentile": pct,
            "tag": tag_label,
            "tier": tier,
        })
    return out


# ── Détection de tendances / outliers ─────────────────────────────────────────

def find_xg_outliers(season: str, league: str | None = None, top_n: int = 5) -> dict:
    """
    Identifie les équipes qui sur/sous-performent par rapport à leur xG.
    Retourne {'over': DataFrame, 'under': DataFrame}.
    """
    std = load_team_season_stats("standard", [season])
    sht = load_team_season_stats("shooting", [season])
    if league and league != "Toutes les ligues":
        std = std[std["league"] == league]
        sht = sht[sht["league"] == league]

    merged = std[["team", "league", "Gls"]].merge(
        sht[["team", "league", "xG"]], on=["team", "league"], how="inner"
    )
    merged["Gls"] = pd.to_numeric(merged["Gls"], errors="coerce")
    merged["xG"] = pd.to_numeric(merged["xG"], errors="coerce")
    merged["Gls-xG"] = (merged["Gls"] - merged["xG"]).round(2)
    merged = merged.dropna(subset=["Gls-xG"]).sort_values("Gls-xG", ascending=False)

    return {
        "over":  merged.head(top_n).reset_index(drop=True),
        "under": merged.tail(top_n).sort_values("Gls-xG").reset_index(drop=True),
    }


def find_defensive_outliers(season: str, league: str | None = None, top_n: int = 5) -> dict:
    """Identifie les meilleures/pires défenses vs leur xGA attendu."""
    kpr = load_team_season_stats("keeper", [season])
    if league and league != "Toutes les ligues":
        kpr = kpr[kpr["league"] == league]

    if "GA" not in kpr.columns:
        return {"best": pd.DataFrame(), "worst": pd.DataFrame()}

    df = kpr[["team", "league", "GA"]].copy()
    df["GA"] = pd.to_numeric(df["GA"], errors="coerce")
    df = df.dropna().sort_values("GA")

    return {
        "best":  df.head(top_n).reset_index(drop=True),
        "worst": df.tail(top_n).sort_values("GA", ascending=False).reset_index(drop=True),
    }


def find_young_stars(
    season: str,
    league: str | None = None,
    max_age: int = 21,
    min_minutes: int = 900,
    top_n: int = 10,
) -> pd.DataFrame:
    """Joueurs U21 avec fort impact offensif (G+A+xAG)."""
    std = load_player_season_stats("standard", [season])
    if league and league != "Toutes les ligues":
        std = std[std["league"] == league]

    df = std.copy()
    df["age_num"] = pd.to_numeric(df["age"], errors="coerce")
    df["min_num"] = pd.to_numeric(df["Min"], errors="coerce")
    df = df[(df["age_num"] <= max_age) & (df["min_num"] >= min_minutes)]

    for c in ("Gls", "Ast", "xG", "xAG"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df["impact"] = df.get("Gls", 0) + df.get("Ast", 0) + df.get("xAG", 0) / 2
    df = df.sort_values("impact", ascending=False).head(top_n)

    cols = ["player", "team", "league", "age", "pos", "Min", "Gls", "Ast", "xG", "xAG", "impact"]
    return df[[c for c in cols if c in df.columns]].reset_index(drop=True)


def find_style_outliers(season: str, league: str | None = None, top_n: int = 5) -> pd.DataFrame:
    """
    Équipes avec le style le plus atypique (distance euclidienne max au centre du cluster).
    """
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    import numpy as np

    cluster_df = build_cluster_data(season, league if league != "Toutes les ligues" else None)
    if cluster_df.empty or len(cluster_df) < 5:
        return pd.DataFrame()

    feature_cols = [c for c in cluster_df.columns if c not in ("team", "league")]
    X = cluster_df[feature_cols].fillna(0).values
    X_scaled = StandardScaler().fit_transform(X)

    km = KMeans(n_clusters=5, random_state=42, n_init=10).fit(X_scaled)
    labels = km.labels_
    centers = km.cluster_centers_
    dists = np.linalg.norm(X_scaled - centers[labels], axis=1)

    out = cluster_df[["team", "league"]].copy()
    out["cluster"] = labels
    out["distance"] = dists.round(2)
    return out.sort_values("distance", ascending=False).head(top_n).reset_index(drop=True)


# ── Similarité ────────────────────────────────────────────────────────────────

def _pos_to_group_simple(pos_str) -> str:
    """FBref pos → FW/MF/DF/GK (dupliqué de components.filters pour ne pas
    créer une dépendance dashboards → components depuis processor)."""
    if pd.isna(pos_str):
        return "MF"
    p = str(pos_str).upper()
    if "GK" in p: return "GK"
    if "FW" in p: return "FW"
    if "DF" in p: return "DF"
    return "MF"


def find_similar_teams(
    team: str,
    season: str,
    league: str | None = None,
    n: int = 5,
) -> pd.DataFrame:
    """
    Retourne les n équipes les plus similaires à `team` en termes de style de jeu.
    Distance euclidienne sur features standardisées (CLUSTER_FEATURES).
    """
    from sklearn.preprocessing import StandardScaler

    league_f = league if league and league != "Toutes les ligues" else None
    df = build_cluster_data(season, league_f)
    if df.empty or team not in df["team"].values:
        return pd.DataFrame()

    feature_cols = [c for c in df.columns if c not in ("team", "league")]
    if not feature_cols:
        return pd.DataFrame()

    X = df[feature_cols].copy()
    X = X.fillna(X.median(numeric_only=True)).fillna(0).values
    Xs = StandardScaler().fit_transform(X)

    pos = df.index[df["team"] == team]
    if len(pos) == 0:
        return pd.DataFrame()
    target = Xs[df.index.get_loc(pos[0])]
    dists = np.linalg.norm(Xs - target, axis=1)

    out = df[["team", "league"]].copy()
    out["distance"] = dists.round(3)
    out["compat_pct"] = out["distance"].apply(distance_to_compat_pct)
    out = (
        out[out["team"] != team]
        .sort_values("compat_pct", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )
    return out


def find_similar_players(
    player: str,
    team: str,
    season: str,
    league: str | None = None,
    pos_group: str | None = None,
    n: int = 5,
    min_minutes: int = 500,
) -> pd.DataFrame:
    """
    Retourne les n joueurs les plus similaires à (player, team) au sein du
    même groupe de position (≥ min_minutes), distance euclidienne sur les
    métriques de poste (PLAYER_METRICS_BY_POS).
    """
    from sklearn.preprocessing import StandardScaler
    from config import PLAYER_METRICS_BY_POS

    league_f = league if league and league != "Toutes les ligues" else None

    metrics = PLAYER_METRICS_BY_POS.get(pos_group or "MF", PLAYER_METRICS_BY_POS["MF"])

    std = load_player_season_stats("standard", [season])
    if league_f:
        std = std[std["league"] == league_f]
    if std.empty:
        return pd.DataFrame()

    std = std.copy()
    std["Min"] = pd.to_numeric(std["Min"], errors="coerce")
    if pos_group:
        std = std[std["pos"].apply(_pos_to_group_simple) == pos_group]
    std = std[std["Min"].fillna(0) >= min_minutes]
    if std.empty:
        return pd.DataFrame()

    base = std[["player", "team", "league", "pos", "age", "Min"]].drop_duplicates(
        subset=["player", "team"]
    ).reset_index(drop=True)

    # Charger toutes les colonnes de métriques de poste
    feature_cols: list[str] = []
    loaded: dict[str, pd.DataFrame] = {}
    for stat_type, col in metrics:
        if stat_type not in loaded:
            df = load_player_season_stats(stat_type, [season])
            if league_f:
                df = df[df["league"] == league_f]
            loaded[stat_type] = df
        df = loaded[stat_type]
        if col not in df.columns:
            continue
        sub = df[["player", "team", col]].drop_duplicates(subset=["player", "team"]).copy()
        sub[col] = pd.to_numeric(sub[col], errors="coerce")
        # Si la colonne existe déjà (collision entre stat_types), on suffixe
        if col in base.columns:
            new_name = f"{col}__{stat_type}"
            sub = sub.rename(columns={col: new_name})
            base = base.merge(sub, on=["player", "team"], how="left")
            feature_cols.append(new_name)
        else:
            base = base.merge(sub, on=["player", "team"], how="left")
            feature_cols.append(col)

    if not feature_cols:
        return pd.DataFrame()

    X = base[feature_cols].copy()
    X = X.fillna(X.median(numeric_only=True)).fillna(0).values
    Xs = StandardScaler().fit_transform(X)

    mask = (base["player"] == player) & (base["team"] == team)
    if not mask.any():
        return pd.DataFrame()
    target_idx = base.index[mask][0]
    target = Xs[base.index.get_loc(target_idx)]
    dists = np.linalg.norm(Xs - target, axis=1)

    out = base[["player", "team", "league", "pos", "age"]].copy()
    out["distance"] = dists.round(3)
    # Échelle adaptée au nombre de features de poste (8-10) → scale plus petit
    out["compat_pct"] = out["distance"].apply(lambda d: distance_to_compat_pct(d, scale=4.5))
    out = (
        out[~mask]
        .sort_values("compat_pct", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )
    return out


# ── Indice de performance par profil (style Data'Scout) ──────────────────────

def _to_per_90(value: float, minutes: float) -> float:
    """Ramène une stat cumulée à 90 minutes."""
    if minutes is None or pd.isna(minutes) or minutes <= 0:
        return 0.0
    return float(value) * 90.0 / float(minutes)


# Stats où on doit travailler en /90 (cumulatives) — les autres sont déjà des taux.
_RATE_STATS = {
    "Cmp%", "Save%", "Tkl%", "Won%", "SoT%", "Succ%", "G/Sh", "G/SoT",
    "Stp%", "Launch%", "AvgLen", "GA90", "PSxG/SoT", "PSxG-GA",
    "Poss", "age", "PrgDist",
}


def compute_profile_scores(
    player: str,
    team: str,
    season: str,
    league: str | None = None,
    min_minutes: int = 1000,
    pos_group: str | None = None,
) -> dict[str, float]:
    """
    Calcule un score /100 par profil compatible avec le poste du joueur.
    Score = moyenne pondérée des percentiles des métriques du profil
    (parmi les joueurs du même groupe pos_group avec ≥ min_minutes).
    Les métriques cumulatives sont automatiquement ramenées à /90.
    """
    from config import PLAYER_PROFILES

    league_f = league if league and league != "Toutes les ligues" else None

    std = load_player_season_stats("standard", [season])
    if league_f:
        std = std[std["league"] == league_f]
    if std.empty:
        return {}

    target_row = std[(std["player"] == player) & (std["team"] == team)]
    if target_row.empty:
        return {}

    if pos_group is None:
        pos_str = target_row["pos"].values[0]
        pos_group = _pos_to_group_simple(pos_str)

    # Pool de référence = joueurs du même groupe avec ≥ min_minutes
    std = std.copy()
    std["Min"] = pd.to_numeric(std["Min"], errors="coerce")
    pool_idx = std[
        (std["pos"].apply(_pos_to_group_simple) == pos_group)
        & (std["Min"].fillna(0) >= min_minutes)
    ][["player", "team", "Min"]].drop_duplicates(subset=["player", "team"])
    if pool_idx.empty:
        return {}

    scores: dict[str, float] = {}
    cache_df: dict[str, pd.DataFrame] = {}

    for profile_name, cfg in PLAYER_PROFILES.items():
        if cfg["pos_group"] != pos_group:
            continue

        weighted_sum = 0.0
        total_weight = 0.0
        for stat_type, col, weight in cfg["metrics"]:
            if stat_type not in cache_df:
                df = load_player_season_stats(stat_type, [season])
                if league_f:
                    df = df[df["league"] == league_f]
                cache_df[stat_type] = df
            df = cache_df[stat_type]
            if col not in df.columns:
                continue

            sub = df[["player", "team", col]].drop_duplicates(subset=["player", "team"])
            sub = sub.merge(pool_idx, on=["player", "team"], how="inner")
            if sub.empty:
                continue

            sub["__val"] = pd.to_numeric(sub[col], errors="coerce")
            # Ramener à /90 si métrique cumulative
            if col not in _RATE_STATS:
                sub["__val"] = sub.apply(
                    lambda r: _to_per_90(r["__val"], r["Min"]) if pd.notna(r["__val"]) else None,
                    axis=1,
                )

            series = sub["__val"].dropna()
            if series.empty:
                continue

            row = sub[(sub["player"] == player) & (sub["team"] == team)]
            if row.empty or pd.isna(row["__val"].values[0]):
                continue
            val = float(row["__val"].values[0])

            pct = percentile_score(series, val)
            w = abs(weight)
            if weight < 0:
                pct = 100 - pct

            weighted_sum += pct * w
            total_weight += w

        if total_weight > 0:
            scores[profile_name] = round(weighted_sum / total_weight, 1)

    return scores


def compute_dominant_profile(
    player: str,
    team: str,
    season: str,
    league: str | None = None,
    min_minutes: int = 1000,
    pos_group: str | None = None,
) -> tuple[str, float, dict[str, float]]:
    """
    Retourne (profil dominant, score, dict complet des scores par profil).
    Utile pour étiqueter automatiquement un joueur ("Box to Box · 83").
    """
    scores = compute_profile_scores(player, team, season, league, min_minutes, pos_group)
    if not scores:
        return ("—", 0.0, {})
    dom = max(scores.items(), key=lambda kv: kv[1])
    return (dom[0], dom[1], scores)


def profile_benchmark_lines(
    season: str,
    league: str | None,
    pos_group: str,
    min_minutes: int = 1000,
) -> dict[str, dict[str, float]]:
    """
    Retourne, pour chaque profil compatible avec pos_group :
      {"top20": score_seuil_top20, "median": score_median}
    calculés sur tous les joueurs du pool.
    Utilisé pour superposer 'Top 20%' et 'Médiane' sur le bar chart profil.
    """
    from config import PLAYER_PROFILES

    league_f = league if league and league != "Toutes les ligues" else None

    std = load_player_season_stats("standard", [season])
    if league_f:
        std = std[std["league"] == league_f]
    if std.empty:
        return {}

    std = std.copy()
    std["Min"] = pd.to_numeric(std["Min"], errors="coerce")
    pool = std[
        (std["pos"].apply(_pos_to_group_simple) == pos_group)
        & (std["Min"].fillna(0) >= min_minutes)
    ][["player", "team"]].drop_duplicates()
    if pool.empty:
        return {}

    out: dict[str, dict[str, float]] = {}
    # On échantillonne max 60 joueurs pour limiter le coût (médiane stable au-delà)
    sample = pool.sample(min(60, len(pool)), random_state=42)
    raw: dict[str, list[float]] = {}

    for _, r in sample.iterrows():
        scores = compute_profile_scores(
            r["player"], r["team"], season, league_f,
            min_minutes=min_minutes, pos_group=pos_group,
        )
        for pname, sc in scores.items():
            raw.setdefault(pname, []).append(sc)

    for pname, vals in raw.items():
        if not vals:
            continue
        s = pd.Series(vals)
        out[pname] = {
            "top20":  round(float(s.quantile(0.8)), 1),
            "median": round(float(s.median()), 1),
        }
    return out


# ── Similarité en pourcentage ────────────────────────────────────────────────

def distance_to_compat_pct(distance: float, scale: float = 6.0) -> float:
    """
    Convertit une distance euclidienne (sur features standardisées) en
    pourcentage de compatibilité ∈ [0, 100].
    Formule : 100 / (1 + d/scale).
    Avec scale=6 (calibration empirique sur 18 features), une distance de 0
    donne 100%, de 6 donne 50%, de 18 donne 25%.
    """
    if distance is None or pd.isna(distance) or distance < 0:
        return 0.0
    return round(100.0 / (1.0 + float(distance) / scale), 1)


# ── Notes par match (rapport de match Data'Scout-style) ──────────────────────

# Pondérations : positives = ce qui contribue à une bonne performance.
_POS_WEIGHTS: dict[str, float] = {
    "Gls":  4.0, "Ast":  3.0, "xG":   2.0, "xAG":  1.5,
    "SCA":  0.3, "GCA":  1.5, "KP":   0.5, "PrgC": 0.1, "PrgP": 0.1,
    "Tkl":  0.3, "TklW": 0.3, "Int":  0.4, "Blocks": 0.3,
    "SoT":  0.5, "Recov": 0.1, "Won": 0.15,
}
_NEG_WEIGHTS: dict[str, float] = {
    "CrdR": 5.0, "CrdY": 1.0, "OG":  4.0, "Fls": 0.3,
    "Err":  3.0, "Mis":  0.2, "Dis": 0.2, "Off": 0.2,
}


def compute_match_ratings(
    player: str,
    team: str,
    season: str,
    league: str | None = None,
) -> pd.DataFrame:
    """
    Calcule une note /10 par match pour un joueur (style Data'Scout).
    Combine actions positives (Gls, Ast, xG, KP, Tkl, Int, ...) et négatives
    (CrdR, CrdY, OG, Fls, Err). Standardise sur les matchs joués par CE joueur :
    note = 5 + 1.5 × z-score, clippée [0, 10].
    Retourne un DataFrame trié par date :
      [date, opponent, venue, result, note, pos_actions, neg_actions, net].
    """
    from data.loader import load_player_match_stats

    df = load_player_match_stats("summary", [season])
    if df.empty:
        return pd.DataFrame()

    league_f = league if league and league != "Toutes les ligues" else None
    if league_f:
        df = df[df["league"] == league_f]

    df = df[(df["player"] == player) & (df["team"] == team)].copy()
    if df.empty:
        return pd.DataFrame()

    # Conversion numérique sûre
    skip_cols = {"date", "game", "venue", "opponent", "result", "league",
                 "season", "team", "player", "round", "day", "match_report",
                 "Notes", "Captain", "Formation", "Referee"}
    for c in df.columns:
        if c not in skip_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df["pos_actions"] = sum(
        df[c] * w for c, w in _POS_WEIGHTS.items() if c in df.columns
    )
    df["neg_actions"] = sum(
        df[c] * w for c, w in _NEG_WEIGHTS.items() if c in df.columns
    )
    df["net"] = df["pos_actions"] - df["neg_actions"]

    if df["net"].std(ddof=0) > 0:
        z = (df["net"] - df["net"].mean()) / df["net"].std(ddof=0)
        df["note"] = (5 + 1.5 * z).clip(0, 10).round(1)
    else:
        df["note"] = 5.0

    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")

    cols = ["date", "opponent", "venue", "result",
            "note", "pos_actions", "neg_actions", "net"]
    return (
        df[[c for c in cols if c in df.columns]]
        .sort_values("date")
        .reset_index(drop=True)
    )


def top_bottom_matches(
    ratings: pd.DataFrame,
    n: int = 3,
) -> dict[str, pd.DataFrame]:
    """Retourne {'top': N meilleurs matchs, 'bottom': N pires} par note."""
    if ratings.empty or "note" not in ratings.columns:
        return {"top": pd.DataFrame(), "bottom": pd.DataFrame()}
    return {
        "top":    ratings.nlargest(n, "note").reset_index(drop=True),
        "bottom": ratings.nsmallest(n, "note").reset_index(drop=True),
    }


# ── Isolation contextuelle équipe (domicile / extérieur) ─────────────────────

def split_team_by_venue(
    team: str,
    season: str,
    league: str | None = None,
) -> pd.DataFrame:
    """Agrégat équipe split par 'Home'/'Away' : J/V/N/D/BP/BC/xG/xGA/Pts."""
    from data.loader import load_team_match_stats, load_team_season_stats

    sched = load_team_match_stats("schedule", [season])
    if sched.empty:
        return pd.DataFrame()

    league_f = league if league and league != "Toutes les ligues" else None
    if league_f:
        std = load_team_season_stats("standard", [season])
        if not std.empty:
            tm = dict(zip(std["team"], std["league"]))
            sched = sched.copy()
            sched["league"] = sched["team"].map(tm).fillna(sched.get("league"))
        sched = sched[sched["league"] == league_f]

    sched = sched[sched["team"] == team].copy()
    if sched.empty or "venue" not in sched.columns:
        return pd.DataFrame()

    sched = sched[sched["result"].isin(["W", "D", "L"])]
    sched["pts"] = sched["result"].map({"W": 3, "D": 1, "L": 0})
    for c in ["GF", "GA", "xG", "xGA"]:
        if c in sched.columns:
            sched[c] = pd.to_numeric(sched[c], errors="coerce")

    grp = sched.groupby("venue", as_index=False).agg(
        J=("result", "count"),
        V=("result", lambda s: int((s == "W").sum())),
        N=("result", lambda s: int((s == "D").sum())),
        D=("result", lambda s: int((s == "L").sum())),
        BP=("GF", "sum"),
        BC=("GA", "sum"),
        xG=("xG", "sum"),
        xGA=("xGA", "sum"),
        Pts=("pts", "sum"),
    )
    grp["±xG"] = (grp["xG"] - grp["xGA"]).round(1)
    return grp


def split_player_by_venue(
    player: str,
    team: str,
    season: str,
    league: str | None = None,
) -> pd.DataFrame:
    """Agrégat joueur split par venue : matchs / Gls / Ast / xG / xAG / note moy."""
    ratings = compute_match_ratings(player, team, season, league)
    if ratings.empty or "venue" not in ratings.columns:
        return pd.DataFrame()

    from data.loader import load_player_match_stats
    summ = load_player_match_stats("summary", [season])
    if summ.empty:
        return pd.DataFrame()
    league_f = league if league and league != "Toutes les ligues" else None
    if league_f:
        summ = summ[summ["league"] == league_f]
    summ = summ[(summ["player"] == player) & (summ["team"] == team)].copy()

    for c in ["Gls", "Ast", "xG", "xAG", "Sh", "SoT"]:
        if c in summ.columns:
            summ[c] = pd.to_numeric(summ[c], errors="coerce")

    summ["date"] = pd.to_datetime(summ.get("date"), errors="coerce")
    merged = summ.merge(
        ratings[["date", "note"]],
        on="date", how="left",
    )

    agg = {"date": "count"}
    for c in ["Gls", "Ast", "xG", "xAG", "Sh", "SoT"]:
        if c in merged.columns:
            agg[c] = "sum"
    if "note" in merged.columns:
        agg["note"] = "mean"

    grp = merged.groupby("venue", as_index=False).agg(agg).rename(
        columns={"date": "Matchs"}
    )
    if "note" in grp.columns:
        grp["note"] = grp["note"].round(2)
    return grp


# ── Évolution multi-saisons d'un joueur ──────────────────────────────────────

def player_profile_evolution(
    player: str,
    season_list: list[str],
    league: str | None = None,
    min_minutes: int = 500,
) -> pd.DataFrame:
    """
    Pour chaque saison où le joueur est présent, calcule les scores des
    profils de son groupe de poste. Retourne DataFrame [season, profile, score, team].
    Un même joueur peut avoir changé d'équipe ; on prend l'équipe principale.
    """
    league_f = league if league and league != "Toutes les ligues" else None
    rows = []
    for s in season_list:
        std = load_player_season_stats("standard", [s])
        if league_f:
            std = std[std["league"] == league_f]
        if std.empty:
            continue
        match = std[std["player"] == player]
        if match.empty:
            continue
        # Équipe avec le plus de minutes cette saison-là
        match = match.copy()
        match["__min"] = pd.to_numeric(match.get("Min", 0), errors="coerce").fillna(0)
        team = match.sort_values("__min", ascending=False).iloc[0]["team"]
        pos_group = _pos_to_group_simple(match.iloc[0]["pos"])

        scores = compute_profile_scores(
            player, team, s, league_f,
            min_minutes=min_minutes, pos_group=pos_group,
        )
        for prof, sc in scores.items():
            rows.append({
                "season": s, "team": team,
                "profile": prof, "score": sc,
            })
    return pd.DataFrame(rows)


# ── Comparaison vs shortlist ─────────────────────────────────────────────────

def compare_to_watchlist(
    target_player: str,
    target_team: str,
    watchlist: list[dict],
    season: str,
    league: str | None = None,
) -> pd.DataFrame:
    """
    Pour chaque joueur de la watchlist, calcule % de compatibilité statistique
    avec le joueur cible. Utilise les métriques du poste du joueur cible.
    """
    from sklearn.preprocessing import StandardScaler
    from config import PLAYER_METRICS_BY_POS

    league_f = league if league and league != "Toutes les ligues" else None

    std = load_player_season_stats("standard", [season])
    if league_f:
        std = std[std["league"] == league_f]
    if std.empty:
        return pd.DataFrame()

    target_row = std[(std["player"] == target_player) & (std["team"] == target_team)]
    if target_row.empty:
        return pd.DataFrame()
    pos_group = _pos_to_group_simple(target_row["pos"].iloc[0])
    metrics = PLAYER_METRICS_BY_POS.get(pos_group, PLAYER_METRICS_BY_POS["MF"])

    pairs = [(target_player, target_team)] + [
        (w["player"], w["team"]) for w in watchlist
        if not (w["player"] == target_player and w["team"] == target_team)
    ]
    if len(pairs) < 2:
        return pd.DataFrame()

    base = pd.DataFrame(pairs, columns=["player", "team"]).reset_index(drop=True)

    feature_cols: list[str] = []
    for stat_type, col in metrics:
        df = load_player_season_stats(stat_type, [season])
        if league_f:
            df = df[df["league"] == league_f]
        if col not in df.columns:
            continue
        sub = df[["player", "team", col]].drop_duplicates(subset=["player", "team"])
        sub[col] = pd.to_numeric(sub[col], errors="coerce")
        new_name = col if col not in base.columns else f"{col}__{stat_type}"
        if new_name != col:
            sub = sub.rename(columns={col: new_name})
        base = base.merge(sub, on=["player", "team"], how="left")
        feature_cols.append(new_name)

    if not feature_cols:
        return pd.DataFrame()

    X = base[feature_cols].copy()
    X = X.fillna(X.median(numeric_only=True)).fillna(0).values
    Xs = StandardScaler().fit_transform(X)
    target_vec = Xs[0]

    out = base.iloc[1:][["player", "team"]].copy()
    out["distance"] = [
        float(((Xs[i] - target_vec) ** 2).sum() ** 0.5)
        for i in range(1, len(Xs))
    ]
    out["compat_pct"] = out["distance"].apply(
        lambda d: distance_to_compat_pct(d, scale=4.5)
    )
    return out.sort_values("compat_pct", ascending=False).reset_index(drop=True)


def parse_score(score_str: str) -> tuple[int, int] | None:
    """'2–1' → (2, 1). Gère les prolongations/tirs au but."""
    if pd.isna(score_str):
        return None
    clean = str(score_str).split("(")[0].strip()
    for sep in ("–", "-", "−"):
        if sep in clean:
            parts = clean.split(sep)
            try:
                return int(parts[0].strip()), int(parts[1].strip())
            except ValueError:
                return None
    return None
