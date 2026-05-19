"""
Nuage de points — Joueurs.

Sélecteur de métriques **catégorisé** via popover (style DataScout).
Toggle labels, K-means avec nommage automatique par quadrant, survol enrichi.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import (
    COLORS, LEAGUE_LABELS, PLOTLY_LAYOUT,
    METRIC_CATEGORIES,
)
from data.loader import load_all_player_season_stats


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_metric_index() -> dict[str, tuple[str, str, str]]:
    flat: dict[str, tuple[str, str, str]] = {}
    for cat, items in METRIC_CATEGORIES.items():
        for label, stat_type, col in items:
            flat[label] = (cat, stat_type, col)
    return flat


@st.cache_data(show_spinner=False)
def _gather_player_metrics(season: str, league_filter: str | None) -> pd.DataFrame:
    stat_types_needed = sorted({stat_type for items in METRIC_CATEGORIES.values()
                                for _, stat_type, _ in items})
    frames = load_all_player_season_stats(stat_types_needed, [season])
    if "standard" not in frames or frames["standard"].empty:
        return pd.DataFrame()

    base = frames["standard"].copy()
    if league_filter:
        base = base[base["league"] == league_filter]

    keys = ["player", "team", "league", "season"]
    for st_name, df in frames.items():
        if st_name == "standard" or df.empty:
            continue
        skip = set(keys) | {"pos", "age", "born", "nation", "url"}
        cols = [c for c in df.columns if c not in skip]
        if not cols:
            continue
        sub = df[keys + cols].copy()
        base = base.merge(sub, on=keys, how="left", suffixes=("", f"_{st_name}"))

    return base


def _metric_picker(axis: str, default_label: str, key_prefix: str,
                   df_columns: set[str], idx_metrics: dict) -> str:
    state_key = f"{key_prefix}_label"
    if state_key not in st.session_state:
        st.session_state[state_key] = default_label
    current = st.session_state[state_key]
    btn_label = f"Axe {axis} : **{current}**"

    with st.popover(btn_label, use_container_width=True):
        cats = list(METRIC_CATEGORIES.keys())
        cat_key = f"{key_prefix}_cat"
        current_cat = idx_metrics.get(current, (cats[0], None, None))[0]
        cat_idx = cats.index(current_cat) if current_cat in cats else 0
        chosen_cat = st.radio("Catégorie", cats, index=cat_idx,
                              key=cat_key, horizontal=False)
        opts = [
            label for label, _, col in METRIC_CATEGORIES[chosen_cat]
            if col in df_columns
        ]
        if not opts:
            st.warning("Aucune métrique disponible.")
            return current
        default_idx = opts.index(current) if current in opts else 0
        chosen = st.radio("Métrique", opts, index=default_idx,
                          key=f"{key_prefix}_metric_radio")
        if st.button("Valider", key=f"{key_prefix}_validate",
                     use_container_width=True, type="primary"):
            st.session_state[state_key] = chosen
            st.rerun()
    return st.session_state[state_key]


# ── Nommage automatique des clusters K-means ─────────────────────────────────

def _name_clusters(centroids: pd.DataFrame, x_col: str, y_col: str,
                   x_label: str, y_label: str) -> dict[str, str]:
    """
    Donne un nom à chaque cluster selon la position relative de son centroïde
    (4 quadrants si possible, plus précis sinon par classement sur chaque axe).
    """
    if centroids.empty:
        return {}

    x_vals = centroids[x_col].values
    y_vals = centroids[y_col].values
    x_med = float(pd.Series(x_vals).median())
    y_med = float(pd.Series(y_vals).median())

    names: dict[str, str] = {}
    for _, row in centroids.iterrows():
        cid = str(row["__cluster"])
        x_high = row[x_col] >= x_med
        y_high = row[y_col] >= y_med
        if x_high and y_high:
            names[cid] = f"⭐  Élites — fort en {x_label} & {y_label}"
        elif x_high and not y_high:
            names[cid] = f"🎯  Spécialistes {x_label}"
        elif y_high and not x_high:
            names[cid] = f"🎯  Spécialistes {y_label}"
        else:
            names[cid] = f"📉  Faibles sur ces 2 axes"
    return names


# ── Render ────────────────────────────────────────────────────────────────────

def render(season: str, league: str) -> None:
    league_filter = None if league == "Toutes les ligues" else league

    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin-bottom:0'>🎯 Nuage de points — Joueurs</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:14px'>"
        f"Choisissez deux statistiques pour explorer la distribution. "
        f"{LEAGUE_LABELS.get(league_filter, league_filter or 'Big 5')} · {season}</div>",
        unsafe_allow_html=True,
    )

    df = _gather_player_metrics(season, league_filter)
    if df.empty:
        st.warning("Pas de données disponibles pour cette saison/ligue.")
        return

    df_cols = set(df.columns)
    idx_metrics = _build_metric_index()

    cX, cY, c_pos, c_min = st.columns([2, 2, 1, 1])
    with cX:
        x_label = _metric_picker("X", "xG", "scp_x", df_cols, idx_metrics)
    with cY:
        y_label = _metric_picker("Y", "Passes décisives", "scp_y", df_cols, idx_metrics)
    with c_pos:
        pos = st.selectbox("Position", ["Tous", "FW", "MF", "DF", "GK"], key="scp_pos")
    with c_min:
        min_min = st.select_slider("Minutes min.", options=[0, 300, 500, 900, 1500, 2000],
                                    value=900, key="scp_min")

    _, _, x_col = idx_metrics[x_label]
    _, _, y_col = idx_metrics[y_label]
    if x_col not in df.columns or y_col not in df.columns:
        st.warning(f"Métrique indisponible : {x_label} ou {y_label}.")
        return

    # ── Filtrage ─────────────────────────────────────────────────────────────
    work = df.copy()
    if pos != "Tous":
        work = work[work["pos"].astype(str).str.contains(pos, na=False)]
    if "Min" in work.columns:
        work["Min"] = pd.to_numeric(work["Min"], errors="coerce")
        work = work[work["Min"].fillna(0) >= min_min]
    work[x_col] = pd.to_numeric(work[x_col], errors="coerce")
    work[y_col] = pd.to_numeric(work[y_col], errors="coerce")
    work = work.dropna(subset=[x_col, y_col])

    if work.empty:
        st.info("Aucun joueur ne correspond aux filtres.")
        return

    # ── Gate "Afficher" : on n'affiche le scatter qu'après clic ──────────────
    from components.filters import render_show_gate
    if not render_show_gate("scatter_player",
                            label="📊  Afficher le nuage",
                            hint="Choisis tes 2 métriques et tes filtres, "
                                 "puis clique pour générer le nuage."):
        return

    # ── Options d'affichage ──────────────────────────────────────────────────
    c_lbl, c_km, c_n_clusters = st.columns([1, 1, 2])
    with c_lbl:
        show_labels = st.toggle("🏷️  Afficher les noms", value=False, key="scp_lbl")
    with c_km:
        use_kmeans = st.toggle("🧬  Clustering K-means", value=False, key="scp_km")
    n_clusters = 4
    if use_kmeans:
        with c_n_clusters:
            n_clusters = st.slider("Nombre de clusters", 2, 8, 4, key="scp_km_n")

    # ── Construction du scatter ──────────────────────────────────────────────
    import plotly.express as px
    import plotly.graph_objects as go

    # Hover data toujours enrichi
    work_plot = work.copy()
    if "age" in work_plot.columns:
        work_plot["age"] = pd.to_numeric(work_plot["age"], errors="coerce").fillna(0).astype(int)
    if "Min" in work_plot.columns:
        work_plot["Min"] = pd.to_numeric(work_plot["Min"], errors="coerce").fillna(0).astype(int)

    hover_data = {}
    for c, lbl in [("player", None), ("team", "Club"), ("pos", "Poste"),
                   ("age", "Âge"), ("Min", "Min."),
                   (x_col, ":.2f"), (y_col, ":.2f")]:
        if c in work_plot.columns:
            hover_data[c] = lbl if lbl is not None else False

    cluster_names: dict[str, str] = {}

    if use_kmeans and len(work_plot) >= n_clusters:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        X = work_plot[[x_col, y_col]].values
        Xs = StandardScaler().fit_transform(X)
        km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
        work_plot["__cluster"] = km.fit_predict(Xs).astype(str)
        centroids = (
            work_plot.groupby("__cluster")[[x_col, y_col]].mean().reset_index()
        )
        cluster_names = _name_clusters(centroids, x_col, y_col, x_label, y_label)
        work_plot["Cluster"] = work_plot["__cluster"].map(cluster_names)

        fig = px.scatter(
            work_plot, x=x_col, y=y_col,
            color="Cluster",
            hover_name="player" if "player" in work_plot.columns else None,
            hover_data=hover_data,
            labels={x_col: x_label, y_col: y_label},
            color_discrete_sequence=px.colors.qualitative.Set2,
            text="player" if show_labels else None,
        )
        # Centroïdes
        centroids["label"] = centroids["__cluster"].map(cluster_names)
        fig.add_trace(go.Scatter(
            x=centroids[x_col], y=centroids[y_col],
            mode="markers",
            marker=dict(size=22, symbol="x", color="white",
                        line=dict(width=2.5, color="black")),
            name="Centroïdes",
            hovertext=centroids["label"],
            hoverinfo="text",
        ))
    else:
        fig = px.scatter(
            work_plot, x=x_col, y=y_col,
            color="pos" if "pos" in work_plot.columns else None,
            hover_name="player" if "player" in work_plot.columns else None,
            hover_data=hover_data,
            labels={x_col: x_label, y_col: y_label, "pos": "Poste"},
            text="player" if show_labels else None,
        )

    fig.update_traces(
        marker=dict(size=10, opacity=0.82, line=dict(width=0.6, color="white")),
        textposition="top center",
        textfont=dict(size=9, color=COLORS["text_muted"]),
        selector=dict(mode="markers" if not show_labels else "markers+text"),
    )
    fig.update_layout(
        **PLOTLY_LAYOUT, height=620,
        title=(
            f"{y_label} vs {x_label} — {len(work_plot)} joueurs"
            + (f" · {n_clusters} clusters" if use_kmeans else "")
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Résumé des clusters (uniquement si K-means actif) ────────────────────
    if use_kmeans and "__cluster" in work_plot.columns:
        st.markdown(
            f"<div style='font-weight:700;color:{COLORS['text']};margin-top:14px;"
            f"margin-bottom:6px'>Composition des clusters</div>",
            unsafe_allow_html=True,
        )
        cluster_summary = (
            work_plot.groupby("__cluster")
                .agg(Effectif=("player", "count"),
                     **{x_label: (x_col, "mean"),
                        y_label: (y_col, "mean")})
                .reset_index()
                .rename(columns={"__cluster": "Cluster #"})
        )
        cluster_summary["Style"] = cluster_summary["Cluster #"].map(cluster_names)
        cluster_summary[x_label] = cluster_summary[x_label].round(2)
        cluster_summary[y_label] = cluster_summary[y_label].round(2)
        cluster_summary = cluster_summary[["Cluster #", "Style", "Effectif",
                                           x_label, y_label]]
        st.dataframe(cluster_summary, use_container_width=True, hide_index=True)
