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
        get_squad_value_season, get_squad_demographics,
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
    def get_squad_value_season(*a, **kw): return None
    def get_squad_demographics(*a, **kw): return pd.DataFrame()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _team_kpis(season: str, league: str | None, team: str, _season_key: str = "") -> list[dict]:
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

    sv = get_squad_value_season(team, _season_key or season, league)
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
    team = select_team(season, league, label="Équipe à analyser", key="team_ctx", show_preview=False)
    if not team:
        return

    _team_header(team, league_label, season, league_filter)
    render_kpi_row(_team_kpis(season, league_filter, team, _season_key=season))

    st.divider()

    tab_card, tab1, tab2, tab3, tab4, tab5, tab6, tab_tm = st.tabs([
        "🎨 Rapport visuel",
        "⚽ Radar Avec ballon",
        "🛡️ Radar Sans ballon",
        "🏅 Percentiles",
        "📊 Indices",
        "🔵 Style de jeu",
        "🔁 Équipes similaires",
        "💶 Transfermarkt",
    ])

    with tab_card:
        from components.report_card import render_club_report_card
        render_club_report_card(team, season, league_filter)

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

    with tab_tm:
        _render_tm_team(team, season, league_filter)


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


# ── Visualisations Transfermarkt (équipe) ─────────────────────────────────────

def _render_tm_team(team: str, season: str, league_filter: str | None) -> None:
    import plotly.graph_objects as go
    import plotly.express as px
    from config import SEASONS, PLOTLY_LAYOUT

    render_section_header(
        "Analyse Transfermarkt de l'effectif",
        "Valeur marchande, démographie et profil de l'effectif — données Transfermarkt.",
    )

    if not TM_AVAILABLE:
        st.info("Module Transfermarkt non disponible.")
        return

    with st.spinner("Chargement des données Transfermarkt…"):
        squad_df = get_squad_demographics(team, league_filter)

    # ── Valeur d'effectif par saison ─────────────────────────────────────────
    season_vals = []
    for sk, sl in SEASONS.items():
        sv = get_squad_value_season(team, sk, league_filter)
        if sv is not None and sv > 0:
            season_vals.append({"Saison": sl, "Valeur (M€)": round(sv / 1e6, 1), "_key": sk})

    if season_vals:
        render_section_header(
            "Évolution de la valeur d'effectif",
            "Snapshots annuels Transfermarkt (fin de saison).",
        )
        sv_df = pd.DataFrame(season_vals).sort_values("_key")
        fig_sv = go.Figure()
        fig_sv.add_trace(go.Bar(
            x=sv_df["Saison"], y=sv_df["Valeur (M€)"],
            marker_color=COLORS["accent_green"],
            marker_line_width=0,
            text=[f"{v:.0f} M€" for v in sv_df["Valeur (M€)"]],
            textposition="outside",
            textfont=dict(color=COLORS["text"]),
            hovertemplate="%{x}<br><b>%{y:.0f} M€</b><extra></extra>",
        ))
        layout_sv = {**PLOTLY_LAYOUT}
        layout_sv["margin"] = dict(l=20, r=20, t=20, b=40)
        fig_sv.update_layout(
            **layout_sv,
            yaxis=dict(title="Valeur (M€)", gridcolor=COLORS["grid"], zeroline=False),
            xaxis=dict(gridcolor=COLORS["grid"]),
            height=300,
        )
        st.plotly_chart(fig_sv, use_container_width=True)

    if squad_df.empty:
        st.info("Aucune donnée démographique disponible pour cet effectif.")
        return

    st.divider()

    # ── Joueurs les plus valorisés ────────────────────────────────────────────
    render_section_header("Top joueurs par valeur marchande")

    if "market_value_in_eur" in squad_df.columns and "name" in squad_df.columns:
        top = (
            squad_df[["name", "market_value_in_eur", "position"]]
            .dropna(subset=["market_value_in_eur"])
            .sort_values("market_value_in_eur", ascending=False)
            .head(10)
            .copy()
        )
        top["Valeur"] = top["market_value_in_eur"].apply(format_value)
        top["Valeur (M€)"] = top["market_value_in_eur"] / 1e6

        if "image_url" in squad_df.columns:
            top = top.merge(squad_df[["name", "image_url"]], on="name", how="left")

        fig_top = go.Figure(go.Bar(
            x=top["Valeur (M€)"],
            y=top["name"],
            orientation="h",
            marker_color=COLORS["accent_gold"],
            marker_line_width=0,
            text=top["Valeur"],
            textposition="outside",
            textfont=dict(color=COLORS["text"], size=10),
            hovertemplate="%{y}<br><b>%{text}</b><extra></extra>",
        ))
        layout_top = {**PLOTLY_LAYOUT}
        layout_top["margin"] = dict(l=20, r=80, t=10, b=20)
        fig_top.update_layout(
            **layout_top,
            xaxis=dict(title="Valeur (M€)", gridcolor=COLORS["grid"], zeroline=False),
            yaxis=dict(autorange="reversed"),
            height=max(280, 35 * len(top)),
            showlegend=False,
        )
        st.plotly_chart(fig_top, use_container_width=True)

    st.divider()

    # ── Démographie ───────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        render_section_header("Distribution des âges")
        if "age" in squad_df.columns:
            ages = squad_df["age"].dropna()
            if not ages.empty:
                fig_age = go.Figure(go.Histogram(
                    x=ages, nbinsx=12,
                    marker_color=COLORS["accent_blue"], marker_line_width=0,
                    hovertemplate="%{x} ans : %{y} joueurs<extra></extra>",
                ))
                layout_age = {**PLOTLY_LAYOUT}
                layout_age["margin"] = dict(l=20, r=20, t=10, b=30)
                fig_age.update_layout(
                    **layout_age,
                    yaxis=dict(gridcolor=COLORS["grid"], zeroline=False, title="Joueurs"),
                    xaxis=dict(gridcolor=COLORS["grid"], title="Âge"),
                    height=280,
                )
                avg_age = ages.mean()
                st.plotly_chart(fig_age, use_container_width=True)
                st.caption(f"Âge moyen : **{avg_age:.1f} ans** · {len(ages)} joueurs")
        else:
            st.info("Données d'âge non disponibles.")

    with c2:
        render_section_header("Nationalités (Top 8)")
        nat_col = "country_of_citizenship" if "country_of_citizenship" in squad_df.columns else None
        if nat_col:
            nat = squad_df[nat_col].dropna().value_counts().head(8)
            if not nat.empty:
                fig_nat = go.Figure(go.Bar(
                    x=nat.values, y=nat.index, orientation="h",
                    marker_color=COLORS["accent_green"], marker_line_width=0,
                    text=nat.values, textposition="outside",
                    textfont=dict(color=COLORS["text"], size=10),
                    hovertemplate="%{y} : %{x} joueurs<extra></extra>",
                ))
                layout_nat = {**PLOTLY_LAYOUT}
                layout_nat["margin"] = dict(l=20, r=40, t=10, b=20)
                fig_nat.update_layout(
                    **layout_nat,
                    xaxis=dict(gridcolor=COLORS["grid"], zeroline=False, title="Joueurs"),
                    yaxis=dict(autorange="reversed"),
                    height=280,
                    showlegend=False,
                )
                st.plotly_chart(fig_nat, use_container_width=True)
        else:
            st.info("Données de nationalité non disponibles.")

    # ── Répartition par poste ─────────────────────────────────────────────────
    if "position" in squad_df.columns:
        render_section_header("Répartition par poste")
        pos_counts = squad_df["position"].dropna().value_counts()
        if not pos_counts.empty:
            pos_colors = [
                COLORS["accent_green"] if "keeper" in p.lower() else
                COLORS["accent_blue"] if "back" in p.lower() else
                COLORS["accent_gold"] if "midfield" in p.lower() else
                COLORS["accent_red"]
                for p in pos_counts.index
            ]
            fig_pos = go.Figure(go.Bar(
                x=pos_counts.index, y=pos_counts.values,
                marker_color=pos_colors, marker_line_width=0,
                text=pos_counts.values, textposition="outside",
                textfont=dict(color=COLORS["text"], size=10),
                hovertemplate="%{x} : %{y} joueurs<extra></extra>",
            ))
            layout_pos = {**PLOTLY_LAYOUT}
            layout_pos["margin"] = dict(l=20, r=20, t=10, b=60)
            fig_pos.update_layout(
                **layout_pos,
                yaxis=dict(gridcolor=COLORS["grid"], zeroline=False, title="Joueurs"),
                xaxis=dict(gridcolor=COLORS["grid"], tickangle=-30),
                height=280, showlegend=False,
            )
            st.plotly_chart(fig_pos, use_container_width=True)

    st.caption("📌 Sources : Transfermarkt (davidcariboo/player-scores)")


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
