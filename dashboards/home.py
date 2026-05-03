"""Dashboard Accueil — page de bienvenue et statistiques globales."""
from __future__ import annotations

import streamlit as st

from config import COLORS, SEASONS, LEAGUES
from components.kpi_cards import render_kpi_row, render_section_header
from data.loader import load_team_season_stats


def render() -> None:
    st.markdown(
        f"""
<div style="text-align:center;padding:30px 0 10px 0">
  <div style="font-size:3rem;font-weight:900;
              background:linear-gradient(90deg,{COLORS['accent_green']},{COLORS['accent_blue']});
              -webkit-background-clip:text;-webkit-text-fill-color:transparent">
    ElevenField
  </div>
  <div style="color:{COLORS['text_muted']};font-size:1rem;margin-top:6px">
    Optimise tes décisions football grâce à la data — Big 5 européens
  </div>
  <div style="color:{COLORS['text']};font-size:0.92rem;margin-top:14px;
              max-width:760px;margin-left:auto;margin-right:auto;line-height:1.6">
    Indice de performance par profil sur <b style="color:{COLORS['accent_green']}">100</b>,
    similarité statistique en <b style="color:{COLORS['accent_blue']}">%</b> de compatibilité,
    radars contextualisés, clustering de styles, comparaisons et shortlist personnelle.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── KPIs globaux ──────────────────────────────────────────────────────────
    df_all = load_team_season_stats("standard")
    if not df_all.empty:
        n_teams = df_all["team"].nunique()
        n_seasons = df_all["season"].nunique()
        n_leagues = df_all["league"].nunique()

        render_kpi_row([
            {"label": "Équipes couvertes",  "value": str(n_teams),    "color": COLORS["accent_green"]},
            {"label": "Saisons disponibles","value": str(n_seasons),  "color": COLORS["accent_blue"]},
            {"label": "Ligues analysées",   "value": str(n_leagues),  "color": COLORS["accent_gold"]},
            {"label": "Source principale",  "value": "FBref",         "color": COLORS["accent_red"]},
        ])

    st.divider()

    # ── Description des modules ───────────────────────────────────────────────
    render_section_header("Modules disponibles")

    modules = [
        {
            "icon": "📊",
            "title": "Base de données",
            "desc": "Classements, leaderboards, exploration avancée. Photos, logos et valeur Transfermarkt.",
        },
        {
            "icon": "🔥",
            "title": "Tendances",
            "desc": "Sur/sous-performeurs xG, jeunes talents, styles atypiques, évolution inter-saisons.",
        },
        {
            "icon": "🏟️",
            "title": "Vue Équipe",
            "desc": "Radars contextualisés, indices composites, clustering de styles, équipes similaires.",
        },
        {
            "icon": "👤",
            "title": "Profil Joueur",
            "desc": "Indice Data'Scout par profil /100, percentiles, radar position, joueurs similaires.",
        },
        {
            "icon": "📅",
            "title": "Analyse Match",
            "desc": "Calendrier, forme récente, évolution xG/xGA match par match.",
        },
        {
            "icon": "⚖️",
            "title": "Comparaison",
            "desc": "Scatter ligue, duel radar joueurs, shortlist personnelle, SHAP, prédiction PPM.",
        },
        {
            "icon": "🧩",
            "title": "Composition",
            "desc": "Crée ton XI sur 7 formations, choisis ton banc, terrain visuel + KPIs cumulés.",
        },
        {
            "icon": "🗂️",
            "title": "Couverture",
            "desc": "Matrice de couverture des données extraites par saison et type de fichier.",
        },
    ]

    cols = st.columns(2)
    for i, mod in enumerate(modules):
        with cols[i % 2]:
            st.markdown(
                f"""
<div style="background:{COLORS['card']};border-radius:12px;padding:16px;margin-bottom:12px;
            border:1px solid {COLORS['border']}">
  <div style="font-size:1.4rem">{mod['icon']}
    <span style="font-size:1rem;font-weight:700;color:{COLORS['text']};margin-left:6px">{mod['title']}</span>
  </div>
  <div style="font-size:0.85rem;color:{COLORS['text_muted']};margin-top:6px">{mod['desc']}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Sources de données ────────────────────────────────────────────────────
    render_section_header("Sources de données")

    season_rows = "".join(
        f"<tr><td style='padding:4px 12px'>{k}</td>"
        f"<td style='padding:4px 12px;color:{COLORS['text_muted']}'>{v}</td></tr>"
        for k, v in SEASONS.items()
    )
    st.markdown(
        f"""
<table style="border-collapse:collapse;margin-top:8px">
  <tr>
    <th style="text-align:left;padding:4px 12px;color:{COLORS['accent_green']}">Code</th>
    <th style="text-align:left;padding:4px 12px;color:{COLORS['accent_green']}">Saison</th>
  </tr>
  {season_rows}
</table>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
<div style="margin-top:16px;font-size:0.83rem;color:{COLORS['text_muted']}">
<b style="color:{COLORS['text']}">FBref</b> (via soccerdata) · Big 5 européens ·
Stats équipe & joueur saison + match · Événements & tirs
</div>
""",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Guide rapide ──────────────────────────────────────────────────────────
    render_section_header("Guide rapide")
    st.markdown(
        f"""
<ol style="color:{COLORS['text_muted']};font-size:0.88rem;line-height:1.8">
  <li>Sélectionnez la <b style="color:{COLORS['text']}">saison</b> et la
      <b style="color:{COLORS['text']}">ligue</b> dans la sidebar.</li>
  <li>Choisissez un <b style="color:{COLORS['text']}">module</b> dans le menu de navigation.</li>
  <li>Affinez les filtres (équipe, joueur, position) selon le module.</li>
  <li>Les graphiques se mettent à jour instantanément.</li>
</ol>
""",
        unsafe_allow_html=True,
    )
