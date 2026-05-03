"""
Dashboard Vue Équipe.
Sélection contextuelle en haut de page (pas de sidebar), radars contextualisés
(Focus + Médiane + Top/Pire 10%), percentiles labellisés, indices de performance
et clustering de style.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from config import (
    COLORS, METRICS_WITH_BALL, METRICS_WITHOUT_BALL,
    CLUSTER_NAMES, PERFORMANCE_INDICES, LEAGUE_LABELS,
)
from components.charts import (
    make_multi_radar, make_labeled_percentile_bars,
    make_performance_index_bars, make_pca_scatter,
)
from components.filters import select_team, select_two_teams
from components.glossary import render_metric_glossary, render_disclaimer
from components.kpi_cards import render_kpi_row, render_section_header
from data.loader import load_team_season_stats
from data.processor import (
    build_radar_with_context, build_percentiles_labeled,
    build_performance_index, build_cluster_data, find_similar_teams,
)

try:
    from transfermarkt.matcher import (
        get_club_logo, match_club, format_value, enrich_with_logos,
    )
    from transfermarkt.loader import load_players
    TM_AVAILABLE = True
except Exception:
    TM_AVAILABLE = False
    def get_club_logo(*a, **kw): return None
    def match_club(*a, **kw): return None
    def format_value(v): return "—"
    def enrich_with_logos(df, *a, **kw): return df
    def load_players(): import pandas as _p; return _p.DataFrame()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _team_kpis(season: str, league: str | None, team: str) -> list[dict]:
    std = load_team_season_stats("standard", [season])
    if league:
        std = std[std["league"] == league]
    row = std[std["team"] == team]
    if row.empty:
        return []
    r = row.iloc[0]

    def fmt(v, d=1):
        try:
            return f"{float(v):.{d}f}"
        except Exception:
            return "—"

    kpis = [
        {"label": "xG",        "value": fmt(r.get("xG", "—")),          "color": COLORS["accent_green"]},
        {"label": "Possession","value": fmt(r.get("Poss", "—")) + "%",  "color": COLORS["accent_blue"]},
        {"label": "PrgP",      "value": fmt(r.get("PrgP", "—"), 0),     "color": COLORS["accent_gold"]},
        {"label": "CrdY",      "value": fmt(r.get("CrdY", "—"), 0),     "color": COLORS["accent_red"]},
    ]

    sv = _squad_value(team, league)
    if sv is not None:
        kpis.insert(0, {"label": "Valeur effectif", "value": format_value(sv),
                        "color": COLORS["accent_gold"]})
    return kpis


def _team_header(team: str, league_label: str, season: str, league_filter: str | None = None) -> None:
    logo_url = get_club_logo(team, league_filter)
    if logo_url:
        c1, c2 = st.columns([1, 9])
        with c1:
            st.image(logo_url, width=70)
        with c2:
            st.markdown(
                f"<div style='padding:6px 0'>"
                f"<span style='font-size:1.45rem;font-weight:800;color:{COLORS['text']}'>{team}</span>"
                f"<div style='font-size:0.85rem;color:{COLORS['text_muted']}'>"
                f"{league_label} · {season}</div></div>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f"<div style='padding:6px 0'>"
            f"<span style='font-size:1.45rem;font-weight:800;color:{COLORS['text']}'>🏟️ {team}</span>"
            f"<span style='font-size:0.85rem;color:{COLORS['text_muted']};margin-left:10px'>"
            f"{league_label} · {season}</span></div>",
            unsafe_allow_html=True,
        )


def _squad_value(team: str, league_filter: str | None) -> float | None:
    """Somme des valeurs marchandes des joueurs du club Transfermarkt matché."""
    club = match_club(team, league_filter)
    if not club:
        return None
    players = load_players()
    if players.empty or "current_club_id" not in players.columns:
        return None
    sub = players[players["current_club_id"] == club["club_id"]]
    if sub.empty or "market_value_in_eur" not in sub.columns:
        return None
    total = pd.to_numeric(sub["market_value_in_eur"], errors="coerce").sum()
    return float(total) if total > 0 else None


# ── Render ────────────────────────────────────────────────────────────────────

def render(season: str, league: str) -> None:
    league_filter = None if league == "Toutes les ligues" else league
    league_label = LEAGUE_LABELS.get(league_filter, league_filter or "Big 5")

    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin-bottom:0'>🏟️ Vue Équipe</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:14px'>"
        f"Profil unique contextualisé ou comparaison directe · {league_label} · {season}</div>",
        unsafe_allow_html=True,
    )

    mode = st.radio(
        "Mode",
        ["🎯 Focus équipe", "⚔️ Comparer 2 équipes"],
        horizontal=True,
        key="team_ov_mode",
        label_visibility="collapsed",
    )

    if mode.startswith("🎯"):
        _render_focus(season, league, league_filter, league_label)
    else:
        _render_versus(season, league, league_filter, league_label)

    render_disclaimer()


# ── Mode Focus ────────────────────────────────────────────────────────────────

def _render_focus(season: str, league: str, league_filter: str | None, league_label: str) -> None:
    team = select_team(season, league, label="Équipe à analyser", key="team_ctx")
    if not team:
        return

    _team_header(team, league_label, season, league_filter)
    render_kpi_row(_team_kpis(season, league_filter, team))

    st.divider()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "⚽ Radar Avec ballon",
        "🛡️ Radar Sans ballon",
        "🏅 Percentiles",
        "📊 Indices",
        "🔵 Style de jeu",
        "🔁 Équipes similaires",
    ])

    with tab1:
        render_section_header(
            "Radar offensif contextualisé",
            "Focus (vert) vs médiane ligue (or), top 10% (bleu) et pire 10% (pointillé).",
        )
        data = build_radar_with_context(METRICS_WITH_BALL, team, "team", season, league_filter)
        if not data["labels"]:
            st.info("Métriques insuffisantes.")
        else:
            st.plotly_chart(make_multi_radar(data, focus_name=team), use_container_width=True)
            render_metric_glossary(metrics=data["labels"])

    with tab2:
        render_section_header(
            "Radar défensif contextualisé",
            "Pressing, récupération et solidité défensive.",
        )
        data = build_radar_with_context(METRICS_WITHOUT_BALL, team, "team", season, league_filter)
        if not data["labels"]:
            st.info("Métriques insuffisantes.")
        else:
            st.plotly_chart(make_multi_radar(data, focus_name=team), use_container_width=True)
            render_metric_glossary(metrics=data["labels"])

    with tab3:
        render_section_header(
            "Percentiles ligue",
            "Top X% = au-dessus de la médiane · Pire X% = en-dessous.",
        )
        all_metrics = {**METRICS_WITH_BALL, **METRICS_WITHOUT_BALL}
        rows = build_percentiles_labeled(all_metrics, team, "team", season, league_filter)
        if not rows:
            st.info("Pas de données de percentile.")
        else:
            rows_sorted = sorted(rows, key=lambda r: r["percentile"], reverse=True)
            st.plotly_chart(
                make_labeled_percentile_bars(rows_sorted, title=f"Percentiles — {team}"),
                use_container_width=True,
            )

    with tab4:
        render_section_header("Indices composites", "Score percentile moyen par groupe.")
        idx_df = build_performance_index([team], season, league_filter)
        st.plotly_chart(make_performance_index_bars(idx_df), use_container_width=True)
        render_metric_glossary(metrics=[], include_indices=True,
                               title="ℹ️ Définition des indices")

        with st.expander("Composition détaillée des indices"):
            for name, metrics in PERFORMANCE_INDICES.items():
                st.markdown(f"**{name}** : " + ", ".join(f"`{col}`" for _, col in metrics))

    with tab5:
        _render_clustering(season, league_filter, highlight=[team])

    with tab6:
        _render_similar_teams(team, season, league_filter)


# ── Mode Versus ───────────────────────────────────────────────────────────────

def _render_versus(season: str, league: str, league_filter: str | None, league_label: str) -> None:
    t1, t2 = select_two_teams(season, league, key_prefix="team_cmp")
    if not t1 or not t2:
        return

    col1, col2 = st.columns(2)
    with col1:
        _team_header(t1, league_label, season, league_filter)
        render_kpi_row(_team_kpis(season, league_filter, t1))
    with col2:
        _team_header(t2, league_label, season, league_filter)
        render_kpi_row(_team_kpis(season, league_filter, t2))

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "⚽ Avec ballon",
        "🛡️ Sans ballon",
        "📊 Indices",
        "🔵 Style de jeu",
    ])

    with tab1:
        render_section_header("Radars offensifs côte-à-côte")
        c1, c2 = st.columns(2)
        with c1:
            d = build_radar_with_context(METRICS_WITH_BALL, t1, "team", season, league_filter)
            if d["labels"]:
                st.plotly_chart(make_multi_radar(d, focus_name=t1), use_container_width=True)
        with c2:
            d = build_radar_with_context(METRICS_WITH_BALL, t2, "team", season, league_filter)
            if d["labels"]:
                st.plotly_chart(make_multi_radar(d, focus_name=t2), use_container_width=True)

    with tab2:
        render_section_header("Radars défensifs côte-à-côte")
        c1, c2 = st.columns(2)
        with c1:
            d = build_radar_with_context(METRICS_WITHOUT_BALL, t1, "team", season, league_filter)
            if d["labels"]:
                st.plotly_chart(make_multi_radar(d, focus_name=t1), use_container_width=True)
        with c2:
            d = build_radar_with_context(METRICS_WITHOUT_BALL, t2, "team", season, league_filter)
            if d["labels"]:
                st.plotly_chart(make_multi_radar(d, focus_name=t2), use_container_width=True)

    with tab3:
        render_section_header("Indices composites")
        idx_df = build_performance_index([t1, t2], season, league_filter)
        st.plotly_chart(make_performance_index_bars(idx_df), use_container_width=True)
        render_metric_glossary(metrics=[], include_indices=True,
                               title="ℹ️ Définition des indices")

    with tab4:
        _render_clustering(season, league_filter, highlight=[t1, t2])


# ── Équipes similaires ────────────────────────────────────────────────────────

def _render_similar_teams(team: str, season: str, league_filter: str | None) -> None:
    render_section_header(
        "Équipes au style le plus proche",
        "Distance euclidienne sur 18 features de style (possession, pressing, "
        "création, défense). Plus la distance est faible, plus le style est proche.",
    )

    n = st.slider("Nombre d'équipes similaires", 3, 15, 5, key="sim_team_n")
    cross_league = st.checkbox(
        "Étendre à toutes les ligues (Big 5)",
        value=(league_filter is None),
        key="sim_team_cross",
        help="Décoche pour rester dans la ligue de l'équipe.",
    )
    league_arg = None if cross_league else league_filter

    with st.spinner("Calcul des similarités…"):
        sim = find_similar_teams(team, season, league_arg, n=n)

    if sim.empty:
        st.info("Pas assez de données de style pour cette équipe.")
        return

    # Enrichissement logos
    sim = enrich_with_logos(sim, team_col="team", league=league_arg)
    sim.insert(0, "Rang", range(1, len(sim) + 1))

    cols = ["Rang"]
    if "logo_url" in sim.columns:
        cols.append("logo_url")
    cols += ["team", "league", "compat_pct"]
    disp = sim[[c for c in cols if c in sim.columns]].rename(columns={
        "logo_url": "Logo", "team": "Équipe", "league": "Ligue",
        "compat_pct": "Compatibilité",
    })

    column_config = {
        "Compatibilité": st.column_config.ProgressColumn(
            "Compatibilité", help="Pourcentage de proximité du style de jeu.",
            format="%.0f %%", min_value=0, max_value=100,
        ),
    }
    if "Logo" in disp.columns:
        column_config["Logo"] = st.column_config.ImageColumn("Logo", width="small")

    st.dataframe(
        disp, use_container_width=True, hide_index=True,
        height=min(48 * len(disp) + 50, 600), column_config=column_config,
    )

    st.caption(
        f"💡 Référence : **{team}** · "
        f"Périmètre : {'Big 5' if cross_league else 'même ligue'}."
    )


# ── Clustering ────────────────────────────────────────────────────────────────

def _render_clustering(season: str, league_filter: str | None, highlight: list[str]) -> None:
    render_section_header(
        "Clustering des styles de jeu",
        "KMeans sur 18 métriques de style, projection PCA 2D.",
    )
    n_clusters = st.slider("Nombre de clusters", 2, 8, 5, key="n_clusters")

    with st.spinner("Calcul du clustering…"):
        cluster_df = build_cluster_data(season, league_filter)

    if cluster_df.empty or len(cluster_df) < n_clusters:
        st.warning("Pas assez de données pour le clustering.")
        return

    feature_cols = [c for c in cluster_df.columns if c not in ("team", "league")]
    X = cluster_df[feature_cols].fillna(0).values

    X_scaled = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X_scaled)

    plot_df = pd.DataFrame({
        "team":    cluster_df["team"].values,
        "league":  cluster_df["league"].values,
        "cluster": labels,
        "PC1":     coords[:, 0],
        "PC2":     coords[:, 1],
    })

    names = {i: CLUSTER_NAMES.get(i, f"Cluster {i}") for i in range(n_clusters)}
    fig = make_pca_scatter(
        plot_df, "PC1", "PC2", "cluster", "team",
        cluster_names=names, title="", highlight=highlight,
    )
    st.plotly_chart(fig, use_container_width=True)

    explained = pca.explained_variance_ratio_
    st.caption(
        f"Variance expliquée : PC1 = {explained[0]*100:.1f}% · "
        f"PC2 = {explained[1]*100:.1f}% · "
        f"Total = {(explained[0]+explained[1])*100:.1f}%"
    )

    with st.expander("Composition des clusters"):
        for c in range(n_clusters):
            teams_in = plot_df[plot_df["cluster"] == c]["team"].tolist()
            st.markdown(f"**{names[c]}** : {', '.join(sorted(teams_in))}")
