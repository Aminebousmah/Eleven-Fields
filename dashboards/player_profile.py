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
from components.design import (
    badge, card_open, card_close, stat_tile, stat_grid,
    pct_color_css, pos_class, gauge_svg, section_header, pin_button,
    pitch_heatmap_svg,
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

    # ──────────────────────────────────────────────────────────────────────────
    # NOUVEAU DESIGN — Header + Row 1 + Row 2 + Row 2.5 (projection + trend)
    # ──────────────────────────────────────────────────────────────────────────
    _render_new_header(player, team, r, season, league_label, photo_url,
                       market_value, nation, foot, flag_html)
    _render_overview_row(player, team, pos_group, season, league_filter, r)
    _render_percentile_bands_row(player, team, pos_group, season, league_filter)
    _render_player_trend_and_evolution(player, team, pos_group, league_filter, r)

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


# ════════════════════════════════════════════════════════════════════════════
# REFONTE v2 — PlayerHeader + Row 1 d'overview (design Claude Design)
# ════════════════════════════════════════════════════════════════════════════

def _render_new_header(player, team, r, season, league_label, photo_url,
                       market_value, nation, foot, flag_html):
    """
    Grand header joueur : photo + identité + KPIs en stat tiles.
    Inspiré de PlayerHeader du bundle.jsx.
    """
    age = r.get("age", "")
    pos = str(r.get("pos", "—"))
    pos_cls = pos_class(pos)

    cols = st.columns([1.3, 4.5, 3.5], gap="medium")
    with cols[0]:
        if photo_url:
            st.image(photo_url, width=140)
        else:
            st.markdown(
                '<div style="width:140px;height:140px;border-radius:14px;'
                'background:var(--bg-2);border:1px solid var(--line);'
                'display:flex;align-items:center;justify-content:center;'
                'font-size:54px;color:var(--ink-3)">👤</div>',
                unsafe_allow_html=True,
            )

    with cols[1]:
        pos_first = pos.split(",")[0].strip() if pos and pos != "—" else ""
        pos_badge = badge(pos_first, pos_cls) if pos_first else ""
        flag_block = (
            f'<span style="margin-left:8px">{flag_html} {nation}</span>'
            if nation else ""
        )
        foot_part = (
            f' <span style="color:var(--ink-3)">· pied {foot}</span>'
            if foot else ""
        )
        st.markdown(
            f'<div style="padding-top:6px">'
            f'  <div style="font-size:28px;font-weight:700;color:var(--ink-0);'
            f'line-height:1.1;letter-spacing:-0.02em">{player}</div>'
            f'  <div style="display:flex;align-items:center;gap:8px;margin-top:8px;'
            f'font-size:12.5px;color:var(--ink-2);flex-wrap:wrap">'
            f'    <span style="font-weight:600;color:var(--ink-1)">{team}</span>'
            f'    <span style="color:var(--ink-4)">·</span>'
            f'    {pos_badge}'
            f'    <span style="color:var(--ink-4)">·</span>'
            f'    <span>{age} ans</span>'
            f'    {flag_block}{foot_part}'
            f'  </div>'
            f'  <div style="font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;'
            f'color:var(--ink-3);margin-top:10px">{league_label} · {season}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with cols[2]:
        def _fmt(v, d=0):
            try:
                return f"{float(v):.{d}f}"
            except Exception:
                return "—"

        mv_str = (
            format_value(market_value)
            if (market_value is not None and pd.notna(market_value))
            else "—"
        )
        tiles = [
            stat_tile("BUTS",     _fmt(r.get("Gls"), 0)),
            stat_tile("PASSES D", _fmt(r.get("Ast"), 0)),
            stat_tile("xG",       _fmt(r.get("xG"), 1)),
            stat_tile("MINUTES",  _fmt(r.get("Min"), 0)),
        ]
        st.markdown(stat_grid(tiles, cols=2, gap="6px"), unsafe_allow_html=True)
        if mv_str != "—":
            st.markdown(
                f'<div class="ef-stat" style="margin-top:6px;background:'
                f'color-mix(in oklch, var(--accent) 14%, var(--bg-2));'
                f'border-color:color-mix(in oklch, var(--accent) 40%, var(--line))">'
                f'  <div class="k" style="color:var(--accent-2)">VALEUR MARCHÉ</div>'
                f'  <div class="v" style="color:var(--accent)">{mv_str}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_overview_row(player, team, pos_group, season, league_filter, r):
    """
    Row 1 du design : 3 cartes côte à côte
      1. Indice de performance (gauge + bandes quintiles)
      2. Top 3 profils tactiques (ranked)
      3. Joueurs similaires (mini cards)
    """
    cols = st.columns([1.2, 2, 1.5], gap="medium")

    # 1. Indice de performance (gauge)
    with cols[0]:
        try:
            top_profile, top_score, all_scores = compute_dominant_profile(
                player, team, season, league_filter,
                pos_group=pos_group, min_minutes=500,
            )
        except Exception:
            top_profile, top_score, all_scores = ("—", 0.0, {})

        st.markdown(card_open("Indice de performance"), unsafe_allow_html=True)
        pin_button(
            f"gauge-{player}", "Indice de performance",
            f"{player} · {top_profile} {top_score:.0f}/100", "gauge",
        )
        st.markdown(
            f'<div style="display:flex;justify-content:center;padding:6px 0 10px">'
            f'{gauge_svg(top_score, max_value=100, label=top_profile, size=140)}'
            f'</div>',
            unsafe_allow_html=True,
        )
        # 5 bandes quintiles
        bands = ["0-19", "20-39", "40-59", "60-79", "80-100"]
        current_band = min(int(top_score // 20), 4) if top_score else 0
        band_colors = ["pct-1", "pct-2", "pct-3", "pct-4", "pct-5"]
        bands_html = ""
        for i, (lbl, col_var) in enumerate(zip(bands, band_colors)):
            is_active = (i == current_band)
            opacity = "60%" if is_active else "18%"
            ink = "var(--ink-0)" if is_active else "var(--ink-3)"
            bands_html += (
                f'<div style="height:26px;border-radius:5px;'
                f'background:color-mix(in oklch, var(--{col_var}) {opacity}, var(--bg-2));'
                f'border:1px solid var(--line-faint);display:flex;align-items:center;'
                f'justify-content:center;font-family:ui-monospace,monospace;'
                f'font-size:10px;color:{ink}">{lbl}</div>'
            )
        st.markdown(
            f'<div style="display:grid;grid-template-columns:repeat(5,1fr);'
            f'gap:4px;margin-top:6px">{bands_html}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="font-size:11px;color:var(--ink-3);margin-top:10px;'
            f'line-height:1.5">Score composite pondéré selon le profil dominant. '
            f'Comparaison vs joueurs {pos_group} (≥ 500 min).</div>',
            unsafe_allow_html=True,
        )
        st.markdown(card_close(), unsafe_allow_html=True)

    # 2. Top 3 profils tactiques
    with cols[1]:
        st.markdown(
            card_open("Top 3 profils tactiques",
                      actions_html='<span style="font-size:10px;color:var(--ink-3)">'
                                   'sur 29 archétypes</span>'),
            unsafe_allow_html=True,
        )
        top3 = (
            sorted(all_scores.items(), key=lambda kv: kv[1], reverse=True)[:3]
            if all_scores else []
        )
        if not top3:
            st.markdown(
                '<div style="font-size:12px;color:var(--ink-3);padding:20px 0;'
                'text-align:center">Pas de profil détecté.</div>',
                unsafe_allow_html=True,
            )
        else:
            for i, (pname, pscore) in enumerate(top3):
                tagline = PLAYER_PROFILES.get(pname, {}).get("tagline", "")
                accent_active = (i == 0)
                bg = ("color-mix(in oklch, var(--accent) 10%, var(--bg-2))"
                      if accent_active else "var(--bg-2)")
                border = ("color-mix(in oklch, var(--accent) 40%, var(--line))"
                          if accent_active else "var(--line-faint)")
                rank_color = "var(--accent)" if accent_active else "var(--ink-3)"
                score_color = pct_color_css(pscore)
                st.markdown(
                    f'<div style="display:grid;grid-template-columns:30px 1fr 70px;'
                    f'gap:12px;align-items:center;padding:10px 12px;border-radius:9px;'
                    f'background:{bg};border:1px solid {border};margin-bottom:6px">'
                    f'  <div style="font-family:ui-monospace,monospace;font-size:18px;'
                    f'font-weight:600;color:{rank_color}">{i+1}</div>'
                    f'  <div>'
                    f'    <div style="font-size:13px;font-weight:600;color:var(--ink-0)">{pname}</div>'
                    f'    <div style="font-size:11px;color:var(--ink-3);margin-top:2px;'
                    f'line-height:1.4">{tagline}</div>'
                    f'  </div>'
                    f'  <div style="text-align:right">'
                    f'    <div style="font-family:ui-monospace,monospace;font-size:20px;'
                    f'font-weight:600;color:{score_color}">{pscore:.0f}</div>'
                    f'    <div style="font-size:9px;letter-spacing:.1em;'
                    f'text-transform:uppercase;color:var(--ink-3)">match</div>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        st.markdown(card_close(), unsafe_allow_html=True)

    # 3. Joueurs similaires
    with cols[2]:
        st.markdown(
            card_open("Joueurs similaires",
                      actions_html='<span style="font-size:10px;color:var(--ink-3)">cosine</span>'),
            unsafe_allow_html=True,
        )
        try:
            sim = find_similar_players(
                player, team, season, league_filter,
                pos_group=pos_group, n=3, min_minutes=500,
            )
        except Exception:
            sim = pd.DataFrame()

        if sim.empty:
            st.markdown(
                '<div style="font-size:12px;color:var(--ink-3);padding:20px 0;'
                'text-align:center">Aucun joueur similaire.</div>',
                unsafe_allow_html=True,
            )
        else:
            sim_enriched = enrich_with_photos(sim.copy(), player_col="player",
                                              league=league_filter)
            for _, srow in sim_enriched.iterrows():
                spname = srow.get("player", "")
                stteam = srow.get("team", "")
                ssim = float(srow.get("compat_pct", 0))
                sphoto = srow.get("image_url")
                age_s = srow.get("age", "")
                photo_html = (
                    f'<img src="{sphoto}" style="width:36px;height:36px;'
                    f'border-radius:50%;object-fit:cover;flex:none"/>'
                    if sphoto and pd.notna(sphoto)
                    else '<div style="width:36px;height:36px;border-radius:50%;'
                         'background:var(--bg-3);display:flex;align-items:center;'
                         'justify-content:center;font-size:18px;flex:none">👤</div>'
                )
                score_color = pct_color_css(ssim)
                st.markdown(
                    f'<div style="display:grid;grid-template-columns:36px 1fr 60px;'
                    f'gap:10px;align-items:center;padding:8px;border-radius:8px;'
                    f'background:var(--bg-2);border:1px solid var(--line-faint);'
                    f'margin-bottom:6px">'
                    f'  {photo_html}'
                    f'  <div style="min-width:0">'
                    f'    <div style="font-size:12.5px;font-weight:500;color:var(--ink-0);'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{spname}</div>'
                    f'    <div style="font-size:10.5px;color:var(--ink-3)">{stteam} · {age_s} ans</div>'
                    f'  </div>'
                    f'  <div style="text-align:right">'
                    f'    <div style="font-family:ui-monospace,monospace;font-size:15px;'
                    f'font-weight:600;color:{score_color}">{ssim:.0f}%</div>'
                    f'    <div style="font-size:9px;color:var(--ink-3)">sim.</div>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        st.markdown(card_close(), unsafe_allow_html=True)


# ─── Row 2 — Percentile bands catégorisés + Strengths/Weaknesses ─────────────

# Bandes de métriques par catégorie (label_fr, stat_type, col, short_label)
_BANDS_BY_POS: dict[str, list[tuple[str, list[tuple[str, str, str]]]]] = {
    "FW": [
        ("FINITION", [
            ("Buts/90",       "standard", "Gls"),
            ("xG/90",         "shooting", "xG"),
            ("Tirs cadrés %", "shooting", "SoT%"),
            ("Conversion %",  "shooting", "G/Sh"),
        ]),
        ("CRÉATION", [
            ("xA/90",       "passing", "xAG"),
            ("Passes clés", "passing", "KP"),
            ("SCA",         "goal_shot_creation", "SCA"),
            ("GCA",         "goal_shot_creation", "GCA"),
        ]),
        ("OFFENSIF", [
            ("Courses prog.", "standard",   "PrgC"),
            ("Reçues prog.",  "standard",   "PrgR"),
            ("Dribbles %",    "possession", "Succ%"),
        ]),
        ("AÉRIEN / PHYSIQUE", [
            ("Duels aériens %", "misc", "Won%"),
            ("Fautes subies",   "misc", "Fld"),
        ]),
    ],
    "MF": [
        ("CONSTRUCTION", [
            ("Précision passes %", "passing",    "Cmp%"),
            ("Passes prog.",       "standard",   "PrgP"),
            ("Touches",            "possession", "Touches"),
            ("Dernier tiers",      "passing",    "1/3"),
        ]),
        ("CRÉATION", [
            ("xA/90",        "passing", "xAG"),
            ("Passes clés",  "passing", "KP"),
            ("SCA",          "goal_shot_creation", "SCA"),
        ]),
        ("DÉFENSE", [
            ("Tacles",         "defense", "Tkl"),
            ("Interceptions",  "defense", "Int"),
            ("Récupérations",  "misc",    "Recov"),
        ]),
        ("OFFENSIF", [
            ("Courses prog.", "standard",   "PrgC"),
            ("Dribbles %",    "possession", "Succ%"),
        ]),
    ],
    "DF": [
        ("DÉFENSE", [
            ("Tacles",         "defense", "Tkl"),
            ("Interceptions",  "defense", "Int"),
            ("Blocs",          "defense", "Blocks"),
            ("Dégagements",    "misc",    "Clr"),
            ("Récupérations",  "misc",    "Recov"),
        ]),
        ("AÉRIEN", [
            ("Duels aériens %", "misc", "Won%"),
            ("Duels gagnés",    "misc", "Won"),
        ]),
        ("CONSTRUCTION", [
            ("Précision passes %", "passing",  "Cmp%"),
            ("Passes prog.",       "standard", "PrgP"),
            ("Dernier tiers",      "passing",  "1/3"),
        ]),
        ("DISCIPLINE", [
            ("Fautes",        "misc",     "Fls"),
            ("Cartons jaunes","standard", "CrdY"),
        ]),
    ],
    "GK": [
        ("ARRÊTS", [
            ("Save %",  "keeper", "Save%"),
            ("CS",      "keeper", "CS"),
        ]),
        ("DISTRIBUTION", [
            ("Précision passes %", "keeper_adv", "Cmp%"),
            ("Longues passes %",   "keeper_adv", "Launch%"),
        ]),
        ("AVANCÉ", [
            ("PSxG - GA",       "keeper_adv", "PSxG-GA"),
            ("PSxG / SoT",      "keeper_adv", "PSxG/SoT"),
        ]),
    ],
}


def _pct_for_metric(player, team, stat_type, col, season, league_filter,
                    pos_group, min_minutes=500):
    """Calcule (valeur brute, percentile 0-100) du joueur sur une métrique."""
    from data.processor import percentile_score, _pos_to_group_simple, _to_per_90, _RATE_STATS

    df = load_player_season_stats(stat_type, [season])
    if league_filter:
        df = df[df["league"] == league_filter]
    if col not in df.columns:
        return None, None

    std = load_player_season_stats("standard", [season])
    if league_filter:
        std = std[std["league"] == league_filter]

    # Pool de référence : même pos_group + minutes minimum
    std = std.copy()
    std["Min"] = pd.to_numeric(std["Min"], errors="coerce")
    pool = std[
        (std["pos"].apply(_pos_to_group_simple) == pos_group)
        & (std["Min"].fillna(0) >= min_minutes)
    ][["player", "team", "Min"]].drop_duplicates(subset=["player", "team"])
    if pool.empty:
        return None, None

    sub = df[["player", "team", col]].drop_duplicates(subset=["player", "team"])
    sub = sub.merge(pool, on=["player", "team"], how="inner")
    if sub.empty:
        return None, None

    sub["__val"] = pd.to_numeric(sub[col], errors="coerce")
    # Ramener à /90 si métrique cumulative
    if col not in _RATE_STATS:
        sub["__val"] = sub.apply(
            lambda x: _to_per_90(x["__val"], x["Min"]) if pd.notna(x["__val"]) else None,
            axis=1,
        )
    series = sub["__val"].dropna()
    if series.empty:
        return None, None

    row = sub[(sub["player"] == player) & (sub["team"] == team)]
    if row.empty or pd.isna(row["__val"].values[0]):
        return None, None

    val = float(row["__val"].values[0])
    pct = percentile_score(series, val)
    return val, pct


def _render_percentile_bands_row(player, team, pos_group, season, league_filter):
    """
    Row 2 : grand bloc 2 colonnes
      - Gauche : Percentile bands groupées par catégorie (style DataScout)
      - Droite : carte Points forts + carte À améliorer (auto-extraits)
    """
    bands = _BANDS_BY_POS.get(pos_group, _BANDS_BY_POS["FW"])

    cols = st.columns([3, 1], gap="medium")

    # ── Gauche : Percentile bands ────────────────────────────────────────────
    with cols[0]:
        # Légende heatmap dans le header de carte
        legend_html = (
            '<div style="display:flex;align-items:center;gap:4px;font-size:10px;'
            'color:var(--ink-3)">Heatmap '
            + "".join(
                f'<div style="width:12px;height:5px;border-radius:1px;'
                f'background:var(--{c})"></div>'
                for c in ["pct-1", "pct-2", "pct-3", "pct-4", "pct-5"]
            )
            + ' <span style="font-family:ui-monospace,monospace">0 → 100</span></div>'
        )
        st.markdown(
            card_open(f"Percentiles par bande · vs. joueurs {pos_group} (≥ 500 min)",
                      actions_html=legend_html),
            unsafe_allow_html=True,
        )

        # Calculer tous les percentiles + collecter pour strengths/weaknesses
        all_metrics = []  # [(label, percentile, value_str), ...]
        bands_data = []
        for band_name, metrics in bands:
            band_rows = []
            for label, stat_type, col in metrics:
                val, pct = _pct_for_metric(player, team, stat_type, col,
                                           season, league_filter, pos_group)
                if pct is None:
                    continue
                value_str = (
                    f"{int(round(val))}" if val == int(val) and abs(val) >= 10
                    else f"{val:.1f}"
                )
                band_rows.append((label, pct, value_str))
                all_metrics.append((label, pct, value_str))
            if band_rows:
                bands_data.append((band_name, band_rows))

        if not bands_data:
            st.markdown(
                '<div style="font-size:12px;color:var(--ink-3);padding:20px 0;'
                'text-align:center">Pas de données suffisantes.</div>',
                unsafe_allow_html=True,
            )
        else:
            # Grille 2 colonnes pour les bandes
            band_cells_html = ""
            for band_name, rows in bands_data:
                avg = sum(p for _, p, _ in rows) / len(rows)
                rows_html = ""
                for lbl, pct, val_str in rows:
                    col_var = pct_color_css(pct)
                    rows_html += (
                        f'<div style="display:grid;grid-template-columns:130px 1fr 36px;'
                        f'gap:8px;align-items:center;height:22px;font-size:11.5px">'
                        f'  <div style="color:var(--ink-1)">{lbl}'
                        f'    <span style="color:var(--ink-3);font-size:10px;margin-left:4px">'
                        f'{val_str}</span></div>'
                        f'  <div style="position:relative;height:6px;'
                        f'background:var(--bg-3);border-radius:3px;overflow:hidden">'
                        f'    <div style="position:absolute;left:0;top:0;bottom:0;'
                        f'width:{pct:.0f}%;background:{col_var};border-radius:3px;'
                        f'box-shadow:0 0 0 1px color-mix(in oklch, {col_var} 50%, transparent)"></div>'
                        f'  </div>'
                        f'  <div style="text-align:right;font-weight:600;'
                        f'color:{col_var};font-family:ui-monospace,monospace">'
                        f'{int(round(pct))}</div>'
                        f'</div>'
                    )
                band_cells_html += (
                    f'<div style="display:flex;flex-direction:column;gap:4px">'
                    f'  <div style="display:flex;align-items:baseline;gap:6px;'
                    f'padding-bottom:4px;border-bottom:1px solid var(--line-faint)">'
                    f'    <span style="font-size:11.5px;font-weight:600;color:var(--ink-1);'
                    f'letter-spacing:.06em;text-transform:uppercase">{band_name}</span>'
                    f'    <span style="color:var(--ink-3);font-family:ui-monospace,monospace;'
                    f'font-size:10px;margin-left:auto">{int(round(avg))} avg</span>'
                    f'  </div>'
                    f'  <div style="display:flex;flex-direction:column;gap:5px;margin-top:6px">'
                    f'  {rows_html}</div>'
                    f'</div>'
                )
            st.markdown(
                f'<div style="display:grid;grid-template-columns:1fr 1fr;'
                f'gap:18px 28px">{band_cells_html}</div>',
                unsafe_allow_html=True,
            )
        st.markdown(card_close(), unsafe_allow_html=True)

    # ── Droite : Points forts / À améliorer ──────────────────────────────────
    with cols[1]:
        if all_metrics:
            strengths = sorted(all_metrics, key=lambda x: x[1], reverse=True)[:4]
            weaknesses = sorted(all_metrics, key=lambda x: x[1])[:3]
        else:
            strengths, weaknesses = [], []

        # Card Points forts
        st.markdown(
            f'<div class="ef-card" style="margin-bottom:10px">'
            f'  <div class="ef-card-hd">'
            f'    <span class="title" style="color:var(--good)">↗ Points forts</span>'
            f'  </div>'
            f'  <ul style="margin:0;padding:0;list-style:none;display:flex;'
            f'flex-direction:column;gap:6px">'
            + "".join(
                f'<li style="display:flex;align-items:center;gap:8px;font-size:12px">'
                f'<span style="width:6px;height:6px;border-radius:1px;'
                f'background:var(--good)"></span>'
                f'<span>{lbl} <span style="color:var(--ink-3);font-family:ui-monospace,monospace;'
                f'margin-left:4px">{int(round(pct))}</span></span></li>'
                for lbl, pct, _ in strengths
            )
            + '</ul></div>',
            unsafe_allow_html=True,
        )

        # Card À améliorer
        st.markdown(
            f'<div class="ef-card">'
            f'  <div class="ef-card-hd">'
            f'    <span class="title" style="color:var(--bad)">↘ À améliorer</span>'
            f'  </div>'
            f'  <ul style="margin:0;padding:0;list-style:none;display:flex;'
            f'flex-direction:column;gap:6px">'
            + "".join(
                f'<li style="display:flex;align-items:center;gap:8px;font-size:12px">'
                f'<span style="width:6px;height:6px;border-radius:1px;'
                f'background:var(--bad)"></span>'
                f'<span>{lbl} <span style="color:var(--ink-3);font-family:ui-monospace,monospace;'
                f'margin-left:4px">{int(round(pct))}</span></span></li>'
                for lbl, pct, _ in weaknesses
            )
            + '</ul></div>',
            unsafe_allow_html=True,
        )


# ─── Row 2.5 — Évolution multi-saisons + projection cross-ligue ──────────────

def _render_player_trend_and_evolution(player, team, pos_group, league_filter, r):
    """
    Row 2.5 : 2 colonnes
      - Évolution multi-saisons : score du profil dominant saison après saison
      - Projection cross-ligue : niveau attendu si transféré dans une autre ligue
    """
    from config import SEASONS, LEAGUE_LABELS, LEAGUES

    # ── Heatmap zones d'activité (mock blobs selon poste) ────────────────────
    st.markdown(card_open("Heatmap · zones d'activité",
                          actions_html='<span style="color:var(--ink-3);'
                                       'font-size:10px">mock (à brancher sur SkillCorner)</span>'),
                unsafe_allow_html=True)

    # Blobs synthétiques selon le pos_group
    blobs_by_pos = {
        "FW": [(30, 22, 18, 0.7), (50, 35, 14, 0.5), (30, 50, 12, 0.4)],
        "MF": [(50, 50, 20, 0.7), (40, 38, 12, 0.5), (60, 38, 12, 0.5),
               (50, 65, 15, 0.55)],
        "DF": [(30, 78, 18, 0.7), (70, 78, 18, 0.65), (50, 88, 14, 0.5)],
        "GK": [(50, 92, 14, 0.8), (50, 80, 10, 0.4)],
    }
    blobs = blobs_by_pos.get(pos_group, blobs_by_pos["MF"])

    pitch_col, info_col = st.columns([1, 2], gap="medium")
    with pitch_col:
        st.markdown(
            f'<div style="display:flex;justify-content:center">'
            f'{pitch_heatmap_svg(blobs, width=200, height=280, direction="up")}</div>',
            unsafe_allow_html=True,
        )
    with info_col:
        st.markdown(
            f'<div style="padding-top:10px;font-size:12px;color:var(--ink-2);'
            f'line-height:1.55">'
            f'Représentation des zones d\'activité préférentielles selon le poste '
            f'générique. Pour une heatmap réelle au mouvement près, il faudrait '
            f'brancher une source de tracking (SkillCorner, StatsBomb 360).'
            f'</div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;'
            f'gap:8px;margin-top:14px">'
            f'  <div class="ef-stat">'
            f'    <div class="k">Zone dominante</div>'
            f'    <div class="v" style="font-size:14px">'
            f'{"Couloir / ⅓ off." if pos_group == "FW" else "Cœur du jeu" if pos_group == "MF" else "Bloc défensif"}'
            f'</div>'
            f'  </div>'
            f'  <div class="ef-stat">'
            f'    <div class="k">Direction d\'attaque</div>'
            f'    <div class="v" style="font-size:14px;color:var(--accent)">▲ Haut</div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown(card_close(), unsafe_allow_html=True)

    cols = st.columns(2, gap="medium")

    # ── Évolution multi-saisons ──────────────────────────────────────────────
    with cols[0]:
        st.markdown(card_open("Évolution multi-saisons",
                              actions_html='<span style="color:var(--ink-3);'
                                           'font-size:10px">score du profil dominant</span>'),
                    unsafe_allow_html=True)
        try:
            evo = player_profile_evolution(
                player, list(SEASONS.keys()), league_filter, min_minutes=500,
            )
        except Exception:
            evo = pd.DataFrame()

        if evo.empty:
            st.markdown(
                '<div style="font-size:12px;color:var(--ink-3);padding:30px 0;'
                'text-align:center">Pas assez de saisons pour visualiser une évolution.</div>',
                unsafe_allow_html=True,
            )
        else:
            import plotly.graph_objects as go
            from config import PLOTLY_LAYOUT
            profile_col = evo.columns[1] if len(evo.columns) > 1 else None
            if profile_col:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=evo["season"], y=evo[profile_col],
                    mode="lines+markers",
                    line=dict(color=COLORS["accent_green"], width=2.5),
                    marker=dict(size=8, color=COLORS["accent_green"],
                                line=dict(color="white", width=1)),
                    fill="tozeroy",
                    fillcolor="rgba(132, 224, 110, 0.10)",
                ))
                fig.update_layout(
                    **PLOTLY_LAYOUT, height=240,
                    showlegend=False,
                    yaxis=dict(range=[0, 100], title="Score /100"),
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown(
                    f'<div style="font-size:10.5px;color:var(--ink-3);'
                    f'text-align:center;margin-top:-10px">Profil : <b>{profile_col}</b></div>',
                    unsafe_allow_html=True,
                )
        st.markdown(card_close(), unsafe_allow_html=True)

    # ── Projection cross-ligue ──────────────────────────────────────────────
    with cols[1]:
        st.markdown(card_open("Projection cross-ligue",
                              actions_html='<span class="ef-badge solid" '
                                           'style="font-size:10px">bêta</span>'),
                    unsafe_allow_html=True)

        current_league = r.get("league", "—")
        other_leagues = [lg for lg in LEAGUES if lg != current_league]

        st.markdown(
            '<div style="font-size:11px;color:var(--ink-3);margin-bottom:10px">'
            'Projection du niveau si transfert vers une autre ligue Big 5. '
            'Pondération basée sur le niveau du championnat cible.</div>',
            unsafe_allow_html=True,
        )

        league_coefs = {
            "ENG-Premier League": 1.00,
            "ESP-La Liga":        0.95,
            "ITA-Serie A":        0.93,
            "GER-Bundesliga":     0.92,
            "FRA-Ligue 1":        0.88,
        }
        cur_coef = league_coefs.get(current_league, 0.90)
        try:
            from data.processor import compute_profile_scores
            scores = compute_profile_scores(player, team, list(SEASONS.keys())[-1],
                                             league=current_league, pos_group=pos_group,
                                             min_minutes=500)
            base_score = max(scores.values()) if scores else 70.0
        except Exception:
            base_score = 70.0

        rows_html = ""
        for lg in other_leagues:
            coef = league_coefs.get(lg, 0.90)
            projected = base_score * (cur_coef / coef)
            projected = max(0, min(100, projected))
            color = pct_color_css(projected)
            rows_html += (
                f'<div style="display:grid;grid-template-columns:1fr 60px 100px;'
                f'gap:10px;align-items:center;padding:10px 4px;'
                f'border-bottom:1px solid var(--line-faint)">'
                f'  <div style="font-size:12.5px;color:var(--ink-1)">'
                f'{LEAGUE_LABELS.get(lg, lg)}</div>'
                f'  <div style="text-align:right;font-family:ui-monospace,monospace;'
                f'font-size:15px;font-weight:700;color:{color}">{projected:.0f}</div>'
                f'  <div style="height:6px;background:var(--bg-3);border-radius:3px;'
                f'overflow:hidden">'
                f'    <div style="width:{projected:.0f}%;height:100%;background:{color}"></div>'
                f'  </div>'
                f'</div>'
            )
        st.markdown(rows_html, unsafe_allow_html=True)
        st.markdown(card_close(), unsafe_allow_html=True)
