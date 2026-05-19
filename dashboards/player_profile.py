"""
Dashboard Profil Joueur.
Sélection contextuelle (position / minutes / recherche / joueur) en haut,
radar multi-références, percentiles labellisés, stats complètes.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import (
    COLORS, PLAYER_METRICS_BY_POS, LEAGUE_LABELS, PLAYER_PROFILES,
    SEASONS, PLOTLY_LAYOUT,
)
from components.charts import make_multi_radar, make_labeled_percentile_bars
from components.filters import select_player
from components.glossary import (
    render_metric_glossary, render_disclaimer,
)
from components.flags import flag_img_html
from components.kpi_cards import render_kpi_row, render_section_header
from data.loader import load_player_season_stats
from data.processor import (
    build_radar_with_context, build_percentiles_labeled, find_similar_players,
    compute_dominant_profile, compute_profile_scores,
    player_profile_evolution,
)

# Module Transfermarkt — optionnel : si dataset absent, fallback silencieux
try:
    from transfermarkt.matcher import (
        match_player, format_value, get_club_logo,
        enrich_with_photos, enrich_with_logos,
        get_player_value_season,
        get_player_value_history, get_player_career_history,
    )
    TM_AVAILABLE = True
except Exception:
    TM_AVAILABLE = False
    def match_player(*a, **kw): return None
    def format_value(v): return "—"
    def get_club_logo(*a, **kw): return None
    def enrich_with_photos(df, *a, **kw): return df
    def enrich_with_logos(df, *a, **kw): return df
    def get_player_value_season(*a, **kw): return None
    def get_player_value_history(*a, **kw): return pd.DataFrame()
    def get_player_career_history(*a, **kw): return pd.DataFrame()


# ── Render ────────────────────────────────────────────────────────────────────

def render(season: str, league: str) -> None:
    league_filter = None if league == "Toutes les ligues" else league
    league_label = LEAGUE_LABELS.get(league_filter, league_filter or "Big 5")

    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin-bottom:0'>👤 Profil Joueur</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:14px'>"
        f"Profil contextualisé par position · {league_label} · {season}</div>",
        unsafe_allow_html=True,
    )

    player, team, pos_group = select_player(season, league, key_prefix="player", show_preview=False)
    if not player:
        return

    # Gate "Afficher" — n'affiche la fiche complète qu'après clic
    from components.filters import render_show_gate
    if not render_show_gate(
        "player_profile",
        label="📊  Afficher la fiche",
        hint="Sélectionne ton joueur ci-dessus, puis clique pour générer l'analyse complète.",
    ):
        return

    # Stats standard
    std = load_player_season_stats("standard", [season])
    if league_filter:
        std = std[std["league"] == league_filter]
    row = std[(std["player"] == player) & (std["team"] == team)]
    if row.empty:
        st.warning(f"Aucune donnée trouvée pour **{player}** ({team}).")
        return
    r = row.iloc[0]

    def fmt(v, d=1):
        try:
            return f"{float(v):.{d}f}"
        except Exception:
            return "—"

    # ── Match Transfermarkt (photo + valeur historique) ──────────────────────
    tm = match_player(player, fbref_league=league_filter)
    photo_url = tm.get("image_url") if tm else None
    # Valeur historique à la fin de la saison sélectionnée
    market_value = get_player_value_season(player, season, league_filter)
    nation = (r.get("nation") or "").split()[-1] if pd.notna(r.get("nation")) else ""
    foot = tm.get("foot") if tm else ""
    flag_html = flag_img_html(nation, size=18) if nation else ""

    # ── En-tête joueur (avec photo si dispo) ─────────────────────────────────
    h1, h2 = st.columns([1, 5]) if photo_url else (None, None)
    if photo_url:
        with h1:
            st.image(photo_url, width=110)
        with h2:
            _nation_part = (
                " &nbsp;·&nbsp; " + flag_html + "&nbsp;" + nation
                if nation else ""
            )
            _foot_part = f" &nbsp;·&nbsp; pied {foot}" if foot else ""
            st.markdown(
                "<div style='padding:4px 0'>"
                "<div style='font-size:1.7rem;font-weight:800;color:" + COLORS["text"] + "'>" + player + "</div>"
                "<div style='font-size:0.9rem;color:" + COLORS["text_muted"] + ";margin-top:4px'>"
                + team + " &nbsp;·&nbsp; " + str(r.get("pos", "—")) + " &nbsp;·&nbsp; " + str(r.get("age", "—")) + " ans"
                + _nation_part + _foot_part
                + "</div>"
                "<div style='font-size:0.8rem;color:" + COLORS["text_muted"] + ";margin-top:2px'>"
                + league_label + " &nbsp;·&nbsp; " + season
                + "</div></div>",
                unsafe_allow_html=True,
            )
    else:
        _nation_part2 = (
            " &nbsp;·&nbsp; " + flag_html + "&nbsp;" + nation
            if nation else ""
        )
        st.markdown(
            "<div style='padding:8px 0 4px 0'>"
            "<div style='font-size:1.6rem;font-weight:800;color:" + COLORS["text"] + "'>" + player + "</div>"
            "<div style='font-size:0.85rem;color:" + COLORS["text_muted"] + ";margin-top:2px'>"
            + team + " &nbsp;·&nbsp; " + str(r.get("pos", "—")) + " &nbsp;·&nbsp; " + str(r.get("age", "—")) + " ans"
            + _nation_part2
            + " &nbsp;·&nbsp; " + league_label + " &nbsp;·&nbsp; " + season
            + "</div></div>",
            unsafe_allow_html=True,
        )

    kpis = [
        {"label": "Buts",     "value": fmt(r.get("Gls", "—"), 0), "color": COLORS["accent_green"]},
        {"label": "Passes D", "value": fmt(r.get("Ast", "—"), 0), "color": COLORS["accent_blue"]},
        {"label": "xG",       "value": fmt(r.get("xG",  "—")),    "color": COLORS["accent_gold"]},
        {"label": "Minutes",  "value": fmt(r.get("Min", "—"), 0), "color": COLORS["accent_red"]},
        {"label": "Matchs",   "value": fmt(r.get("MP",  "—"), 0), "color": COLORS["text_muted"]},
    ]
    if market_value is not None and pd.notna(market_value):
        kpis.insert(0, {"label": "Valeur marchande", "value": format_value(market_value),
                        "color": COLORS["accent_gold"]})
    render_kpi_row(kpis)

    st.divider()

    tab0, tab_card, tab1, tab2, tab3, tab4, tab_evo, tab_exp = st.tabs([
        "📊 Indice Data'Scout",
        "🎨 Rapport visuel",
        "🎯 Radar contextualisé",
        "🏅 Percentiles",
        "📋 Stats complètes",
        "🔁 Joueurs similaires",
        "📈 Évolution multi-saisons",
        "📄 Export rapport",
    ])

    with tab0:
        _render_profile_index(player, team, pos_group, season, league_filter)

    with tab_card:
        from components.report_card import render_player_report_card
        render_player_report_card(player, team, pos_group, season, league_filter)

    metrics = PLAYER_METRICS_BY_POS.get(pos_group, PLAYER_METRICS_BY_POS["MF"])

    with tab1:
        render_section_header(
            f"Radar — {pos_group}",
            "Focus (vert) vs médiane (or), top 10% (bleu) et pire 10% (pointillé) des joueurs de même position.",
        )
        data = build_radar_with_context(
            metrics, player, "player", season, league_filter, min_minutes=500,
        )
        if not data["labels"]:
            st.warning("Métriques insuffisantes.")
        else:
            st.plotly_chart(make_multi_radar(data, focus_name=player), use_container_width=True)
            render_metric_glossary(metrics=data["labels"])

    with tab2:
        render_section_header(
            "Percentiles ligue",
            "Position dans la distribution des joueurs de même position (≥ 500 minutes).",
        )
        rows = build_percentiles_labeled(
            metrics, player, "player", season, league_filter, min_minutes=500,
        )
        if not rows:
            st.warning("Pas de données de percentile.")
        else:
            rows_sorted = sorted(rows, key=lambda r: r["percentile"], reverse=True)
            st.plotly_chart(
                make_labeled_percentile_bars(rows_sorted, title=f"Percentiles — {player}"),
                use_container_width=True,
            )
            render_metric_glossary(metrics=[r["metric"] for r in rows_sorted])

    with tab3:
        render_section_header("Stats saison complètes")
        stat_labels = {
            "standard": "Standard", "shooting": "Tirs", "passing": "Passes",
            "goal_shot_creation": "Créations", "defense": "Défense",
            "possession": "Possession", "misc": "Divers",
        }
        skip = {"league", "season", "team", "player", "nation", "pos",
                "age", "born", "url", "match_report"}
        for st_type, label in stat_labels.items():
            df = load_player_season_stats(st_type, [season])
            if league_filter:
                df = df[df["league"] == league_filter]
            df = df[(df["team"] == team) & (df["player"] == player)]
            if df.empty:
                continue
            show_cols = [c for c in df.columns if c not in skip]
            if not show_cols:
                continue
            with st.expander(label):
                st.dataframe(
                    df[show_cols].reset_index(drop=True)
                    .style.format("{:.2f}", na_rep="—"),
                    use_container_width=True,
                )

    with tab4:
        render_section_header(
            "Profils les plus proches",
            f"Distance euclidienne sur les métriques du poste {pos_group} "
            f"(joueurs avec ≥ 500 minutes).",
        )
        c1, c2 = st.columns([1, 2])
        with c1:
            n_sim = st.slider("Nombre", 3, 15, 6, key="sim_player_n")
        with c2:
            cross_league = st.checkbox(
                "Étendre à toutes les ligues (Big 5)",
                value=(league_filter is None),
                key="sim_player_cross",
            )
        league_arg = None if cross_league else league_filter

        with st.spinner("Recherche des joueurs similaires…"):
            sim = find_similar_players(
                player, team, season, league_arg,
                pos_group=pos_group, n=n_sim, min_minutes=500,
            )

        if sim.empty:
            st.info("Pas assez de données pour calculer la similarité.")
        else:
            sim = enrich_with_photos(sim, player_col="player", league=league_arg)
            sim = enrich_with_logos(sim, team_col="team", league=league_arg)
            if "market_value_in_eur" in sim.columns:
                sim["Valeur"] = sim["market_value_in_eur"].apply(format_value)

            for rank, (_, row) in enumerate(sim.iterrows(), start=1):
                _render_similar_card(rank, row, season, league_arg)

            st.caption(
                f"💡 Référence : **{player}** ({team}) · "
                f"Périmètre : {'Big 5' if cross_league else 'même ligue'} · "
                f"Position : {pos_group}."
            )

    with tab_evo:
        _render_evolution(player, team, pos_group, league_filter)

    with tab_exp:
        _render_export(player, team, pos_group, season, league_filter, league_label, r)

    render_disclaimer()


# ── Indice de performance Data'Scout ──────────────────────────────────────────

def _render_profile_index(
    player: str, team: str, pos_group: str,
    season: str, league_filter: str | None,
) -> None:
    render_section_header(
        "Indice de performance par profil",
        "Score /100 calculé sur les métriques du profil, parmi les joueurs de "
        "même position avec ≥ 1000 minutes. Le profil dominant est celui où le "
        "joueur surperforme le plus.",
    )

    with st.spinner("Calcul des scores par profil…"):
        dominant, dom_score, all_scores = compute_dominant_profile(
            player, team, season, league_filter,
            min_minutes=1000, pos_group=pos_group,
        )

    if not all_scores:
        st.warning(
            "Pas assez de données pour calculer l'indice de profil. "
            "Réessaie sur une saison complète (avec stats avancées)."
        )
        return

    # ── Bandeau profil dominant ─────────────────────────────────────────────
    tagline = PLAYER_PROFILES.get(dominant, {}).get("tagline", "")
    badge_color = (
        COLORS["accent_green"] if dom_score >= 70 else
        COLORS["accent_gold"]  if dom_score >= 50 else
        COLORS["accent_red"]
    )
    st.markdown(
        f"<div style='padding:14px 16px;background:{COLORS['card']};"
        f"border-left:4px solid {badge_color};border-radius:10px;margin-bottom:14px'>"
        f"<div style='font-size:0.78rem;color:{COLORS['text_muted']};"
        f"text-transform:uppercase;letter-spacing:0.06em'>Profil dominant</div>"
        f"<div style='font-size:1.5rem;font-weight:800;color:{COLORS['text']};margin-top:2px'>"
        f"{dominant} <span style='color:{badge_color}'>· {dom_score:.1f}/100</span></div>"
        f"<div style='font-size:0.85rem;color:{COLORS['text_muted']};margin-top:4px'>{tagline}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Bar chart : score par profil ────────────────────────────────────────
    import plotly.graph_objects as go
    from config import PLOTLY_LAYOUT

    profiles = list(all_scores.keys())
    scores = [all_scores[p] for p in profiles]
    bar_colors = [
        COLORS["accent_green"] if s >= 75 else
        "#7ed957" if s >= 50 else
        COLORS["accent_gold"] if s >= 25 else
        COLORS["accent_red"]
        for s in scores
    ]

    fig = go.Figure(go.Bar(
        x=scores, y=profiles, orientation="h",
        marker_color=bar_colors, marker_line_width=0,
        text=[f"{s:.1f}" for s in scores],
        textposition="outside",
        textfont=dict(color=COLORS["text"]),
        hovertemplate="%{y}<br>Score : %{x:.1f}/100<extra></extra>",
    ))
    # Ligne médiane à 50
    fig.add_shape(
        type="line", x0=50, x1=50, y0=-0.5, y1=len(profiles) - 0.5,
        line=dict(color=COLORS["text_muted"], width=1, dash="dash"),
    )

    layout = {**PLOTLY_LAYOUT}
    layout["margin"] = dict(l=20, r=80, t=20, b=30)
    fig.update_layout(
        **layout,
        xaxis=dict(range=[0, 110], title="Score (0 = pire, 100 = meilleur)",
                   gridcolor=COLORS["grid"], zeroline=False),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12)),
        height=max(300, len(profiles) * 56),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Détail des métriques pondérées du profil dominant ───────────────────
    cfg = PLAYER_PROFILES.get(dominant, {})
    if cfg.get("metrics"):
        with st.expander(f"Composition du profil « {dominant} »"):
            for stat_type, col, w in cfg["metrics"]:
                sign = "↑" if w > 0 else "↓"
                weight_pct = abs(w) / sum(abs(m[2]) for m in cfg["metrics"]) * 100
                st.markdown(
                    f"- `{col}` ({stat_type}) {sign} · "
                    f"<span style='color:{COLORS['text_muted']}'>"
                    f"poids : {weight_pct:.0f}%</span>",
                    unsafe_allow_html=True,
                )


# ── Évolution multi-saisons (style Gyökeres dans la plaquette) ───────────────

def _render_evolution(player: str, team: str, pos_group: str,
                      league_filter: str | None) -> None:
    render_section_header(
        "Évolution des indices de performance",
        f"Score /100 du joueur sur chaque saison disponible, par profil {pos_group}. "
        "Permet de voir si un joueur progresse sur un rôle donné.",
    )

    seasons = list(SEASONS.keys())
    with st.spinner("Calcul des indices saison par saison…"):
        evo = player_profile_evolution(player, seasons, league_filter, min_minutes=500)

    if evo.empty:
        st.info(
            "Pas de données suffisantes pour tracer l'évolution. "
            "Le joueur doit avoir ≥ 500 minutes sur au moins 2 saisons."
        )
        return

    # ── Line chart : un trait par profil
    import plotly.graph_objects as go
    fig = go.Figure()
    profiles = evo["profile"].unique().tolist()
    for i, prof in enumerate(profiles):
        sub = evo[evo["profile"] == prof].sort_values("season")
        color = list(COLORS.values())[(i + 4) % 8]
        fig.add_trace(go.Scatter(
            x=[SEASONS.get(s, s) for s in sub["season"]],
            y=sub["score"],
            mode="lines+markers",
            name=prof,
            line=dict(width=2.5),
            marker=dict(size=10, line=dict(color="#fff", width=1)),
            hovertemplate="%{x}<br>" + prof + " : %{y:.1f}/100<extra></extra>",
        ))

    layout = {**PLOTLY_LAYOUT}
    layout["margin"] = dict(l=20, r=20, t=20, b=30)
    layout["legend"] = dict(
        orientation="h", yanchor="bottom", y=-0.25,
        xanchor="center", x=0.5, font=dict(size=10),
    )
    fig.update_layout(
        **layout,
        yaxis=dict(range=[0, 100], gridcolor=COLORS["grid"], title="Score /100"),
        xaxis=dict(gridcolor=COLORS["grid"]),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Table récap : profil dominant par saison
    pivot = evo.loc[evo.groupby("season")["score"].idxmax()].copy()
    pivot["Saison"] = pivot["season"].map(lambda s: SEASONS.get(s, s))
    pivot = pivot.rename(columns={
        "team": "Équipe", "profile": "Profil dominant", "score": "Score",
    })[["Saison", "Équipe", "Profil dominant", "Score"]]
    cfg = {"Score": st.column_config.ProgressColumn(
        "Score", format="%.0f / 100", min_value=0, max_value=100,
    )}
    st.dataframe(pivot, hide_index=True, use_container_width=True,
                 column_config=cfg)


# ── Export rapport markdown ──────────────────────────────────────────────────

# ── Carte joueur similaire (style ranking) ───────────────────────────────────

def _render_similar_card(rank: int, row: pd.Series,
                         season: str, league_filter: str | None) -> None:
    """Carte horizontale : rang + photo + infos + compat circulaire + bouton fiche."""
    compat = float(row.get("compat_pct", 0))
    player_name = row.get("player", "")
    team_name = row.get("team", "")
    league_name = row.get("league", "")
    age = row.get("age", "")
    pos = row.get("pos", "")
    photo = row.get("image_url")
    logo = row.get("logo_url")
    valeur = row.get("Valeur", "")

    # Couleur du score circulaire selon la valeur
    if   compat >= 90: score_color = "#00ff99"
    elif compat >= 75: score_color = "#7cd86b"
    elif compat >= 60: score_color = "#ffd700"
    elif compat >= 45: score_color = "#ff9f43"
    else:              score_color = "#ff4655"

    # Rang
    if rank == 1:   rank_bg, rank_c = COLORS["accent_gold"], "#1a1a2e"
    elif rank == 2: rank_bg, rank_c = "#c5cce0", "#1a1a2e"
    elif rank == 3: rank_bg, rank_c = "#cd853f", "#fff"
    else:           rank_bg, rank_c = COLORS["card"], COLORS["text_muted"]

    with st.container(border=True):
        c_rank, c_photo, c_info, c_score, c_btn = st.columns(
            [0.6, 0.9, 4.4, 0.8, 1.6]
        )

        with c_rank:
            st.markdown(
                f"<div style='background:{rank_bg};color:{rank_c};"
                f"border-radius:8px;width:46px;height:46px;display:flex;"
                f"align-items:center;justify-content:center;font-weight:900;"
                f"font-size:0.95rem'>#{rank}</div>",
                unsafe_allow_html=True,
            )

        with c_photo:
            if photo and pd.notna(photo):
                st.image(photo, width=60)
            else:
                st.markdown(
                    f"<div style='width:60px;height:60px;border-radius:50%;"
                    f"background:{COLORS['border']};display:flex;align-items:center;"
                    f"justify-content:center;font-size:28px'>👤</div>",
                    unsafe_allow_html=True,
                )

        with c_info:
            tags = []
            if pos and pd.notna(pos):
                first_pos = str(pos).split(",")[0].strip()
                tags.append(
                    f"<span style='background:{COLORS['border']};color:{COLORS['text']};"
                    f"padding:2px 8px;border-radius:10px;font-size:0.72rem;"
                    f"font-weight:600;margin-right:5px'>{first_pos}</span>"
                )
            if age and pd.notna(age):
                try:
                    tags.append(
                        f"<span style='color:{COLORS['text_muted']};font-size:0.78rem;"
                        f"margin-right:12px'>👤 {int(float(age))} ans</span>"
                    )
                except Exception:
                    pass
            if valeur and valeur not in ("—", ""):
                tags.append(
                    f"<span style='background:{COLORS['accent_gold']}20;"
                    f"color:{COLORS['accent_gold']};padding:2px 8px;border-radius:10px;"
                    f"font-size:0.72rem;font-weight:700;margin-right:5px'>"
                    f"💰 {valeur}</span>"
                )
            meta_html = " ".join(tags) if tags else ""

            logo_html = ""
            if logo and pd.notna(logo):
                logo_html = (
                    f"<img src='{logo}' style='height:18px;width:18px;"
                    f"object-fit:contain;vertical-align:middle;margin-right:6px'>"
                )

            st.markdown(
                f"<div style='display:flex;flex-direction:column;gap:4px'>"
                f"  <div style='font-size:1.05rem;font-weight:700;color:{COLORS['text']}'>"
                f"    {player_name}"
                f"  </div>"
                f"  <div style='font-size:0.85rem;color:{COLORS['text_muted']}'>"
                f"    {logo_html}{team_name}"
                f"    <span style='margin-left:10px'>· {LEAGUE_LABELS.get(league_name, league_name)}</span>"
                f"  </div>"
                f"  <div style='margin-top:4px'>{meta_html}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with c_score:
            pct = int(round(compat))
            bg = COLORS["card"]
            st.markdown(
                f"<div style='width:62px;height:62px;border-radius:50%;"
                f"background:conic-gradient({score_color} 0% {pct}%, {bg} {pct}% 100%);"
                f"display:flex;align-items:center;justify-content:center'>"
                f"<div style='width:48px;height:48px;border-radius:50%;"
                f"background:{COLORS['surface']};display:flex;align-items:center;"
                f"justify-content:center;font-weight:900;font-size:0.95rem;"
                f"color:{score_color}'>{pct}%</div></div>",
                unsafe_allow_html=True,
            )

        with c_btn:
            uid = f"{rank}_{player_name}_{team_name}".replace(" ", "_")
            if st.button("→  Voir la fiche", key=f"btn_sim_{uid}",
                         use_container_width=True):
                # Navigation programmatique vers l'Analyse Joueur de ce joueur
                st.session_state["mode"] = "player"
                st.session_state["mode_radio"] = "👤  Joueurs"
                st.session_state["nav_radio"] = "👤  Analyse Joueurs"
                st.session_state["ctx_player"] = player_name
                st.session_state["ctx_team"] = team_name
                st.session_state["_selected_player"] = player_name
                st.rerun()


def _render_export(player: str, team: str, pos_group: str,
                   season: str, league_filter: str | None,
                   league_label: str, r: pd.Series) -> None:
    render_section_header(
        "Export rapport markdown",
        "Génère un rapport texte de référence (lisible et imprimable) "
        "synthétisant les données du joueur.",
    )

    st.caption(
        "Le rapport reprend : identité, KPIs, profil dominant, scores par profil, "
        "joueurs similaires (top 5)."
    )

    if st.button("📄 Générer le rapport", key="exp_btn", type="primary"):
        with st.spinner("Génération du rapport…"):
            md = _build_markdown_report(
                player, team, pos_group, season, league_filter, league_label, r,
            )
        st.success("Rapport prêt.")
        st.download_button(
            "💾 Télécharger le rapport (.md)",
            data=md.encode("utf-8"),
            file_name=f"rapport_{player.replace(' ', '_')}_{season}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        with st.expander("Aperçu", expanded=True):
            st.markdown(md)


def _build_markdown_report(player: str, team: str, pos_group: str,
                            season: str, league_filter: str | None,
                            league_label: str, r: pd.Series) -> str:
    """Construit un rapport markdown complet."""
    lines: list[str] = []
    season_label = SEASONS.get(season, season)

    # Header
    lines.append(f"# Rapport joueur — {player}")
    lines.append("")
    lines.append(f"**Équipe** : {team}  ")
    lines.append(f"**Position** : {r.get('pos', '—')} ({pos_group})  ")
    lines.append(f"**Âge** : {r.get('age', '—')}  ")
    lines.append(f"**Ligue** : {league_label}  ")
    lines.append(f"**Saison** : {season_label}  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # KPIs (la seule vue où on AFFICHE encore les minutes)
    lines.append("## Statistiques saison")
    lines.append("")
    for label, key in [("Buts", "Gls"), ("Passes décisives", "Ast"),
                       ("xG", "xG"), ("Minutes", "Min"), ("Matchs", "MP")]:
        val = r.get(key, "—")
        try:
            val = f"{float(val):.1f}" if isinstance(val, (int, float)) or str(val).replace('.', '').isdigit() else val
        except Exception:
            pass
        lines.append(f"- **{label}** : {val}")
    lines.append("")

    # Profil dominant
    dominant, dom_score, all_scores = compute_dominant_profile(
        player, team, season, league_filter, min_minutes=1000, pos_group=pos_group,
    )
    if all_scores:
        tagline = PLAYER_PROFILES.get(dominant, {}).get("tagline", "")
        lines.append(f"## Indice de performance — Profil dominant")
        lines.append("")
        lines.append(f"### {dominant} · {dom_score:.1f}/100")
        if tagline:
            lines.append(f"> *{tagline}*")
        lines.append("")
        lines.append("**Scores par profil compatible :**")
        lines.append("")
        for prof, sc in sorted(all_scores.items(), key=lambda kv: kv[1], reverse=True):
            bar = "█" * int(sc / 5) + "░" * (20 - int(sc / 5))
            lines.append(f"- `{prof:24s}` `{bar}` {sc:.1f}/100")
        lines.append("")

    # Joueurs similaires (top 5)
    sim = find_similar_players(
        player, team, season, league_filter,
        pos_group=pos_group, n=5, min_minutes=500,
    )
    if not sim.empty:
        lines.append("## Joueurs au profil similaire (top 5)")
        lines.append("")
        lines.append("| Rang | Joueur | Équipe | Compatibilité |")
        lines.append("|------|--------|--------|---------------|")
        for i, row in sim.iterrows():
            lines.append(
                f"| {i+1} | {row['player']} | {row['team']} | "
                f"{row['compat_pct']:.0f}% |"
            )
        lines.append("")

    # Disclaimer
    from config import DISCLAIMER
    lines.append("---")
    lines.append("")
    lines.append("> ⚠️ " + DISCLAIMER)
    lines.append("")
    lines.append(f"*Rapport généré par ElevenField · {season_label}*")

    return "\n".join(lines)
