"""
Dashboard Composition — créer une équipe type.
Choix de la formation, des 11 titulaires et des 7 remplaçants, avec
visualisation sur un terrain et synthèse des stats cumulées.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import COLORS, LEAGUE_LABELS, PLOTLY_LAYOUT
from components.kpi_cards import render_kpi_row, render_section_header
from data.loader import load_player_season_stats

try:
    from transfermarkt.matcher import (
        match_player, get_club_logo, format_value,
    )
    TM_AVAILABLE = True
except Exception:
    TM_AVAILABLE = False
    def match_player(*a, **kw): return None
    def get_club_logo(*a, **kw): return None
    def format_value(v): return "—"


# ── Formations : (groupe FBref, label rôle, x, y) ─────────────────────────────
# Repère : terrain 0–100 × 0–100, but adverse en haut (y=100), GK en bas (y=8).

FORMATIONS: dict[str, list[tuple[str, str, float, float]]] = {
    "4-3-3": [
        ("GK", "GK", 50, 8),
        ("DF", "LB", 12, 28), ("DF", "CB", 38, 25), ("DF", "CB", 62, 25), ("DF", "RB", 88, 28),
        ("MF", "CM", 25, 52), ("MF", "MC", 50, 50), ("MF", "CM", 75, 52),
        ("FW", "LW", 18, 80), ("FW", "ST", 50, 86), ("FW", "RW", 82, 80),
    ],
    "4-4-2": [
        ("GK", "GK", 50, 8),
        ("DF", "LB", 12, 28), ("DF", "CB", 38, 25), ("DF", "CB", 62, 25), ("DF", "RB", 88, 28),
        ("MF", "LM", 14, 55), ("MF", "CM", 38, 52), ("MF", "CM", 62, 52), ("MF", "RM", 86, 55),
        ("FW", "ST", 38, 82), ("FW", "ST", 62, 82),
    ],
    "4-2-3-1": [
        ("GK", "GK", 50, 8),
        ("DF", "LB", 12, 28), ("DF", "CB", 38, 25), ("DF", "CB", 62, 25), ("DF", "RB", 88, 28),
        ("MF", "DM", 36, 48), ("MF", "DM", 64, 48),
        ("MF", "LW", 18, 70), ("MF", "AM", 50, 70), ("MF", "RW", 82, 70),
        ("FW", "ST", 50, 88),
    ],
    "3-5-2": [
        ("GK", "GK", 50, 8),
        ("DF", "CB", 25, 25), ("DF", "CB", 50, 22), ("DF", "CB", 75, 25),
        ("MF", "LWB", 10, 50), ("MF", "CM", 32, 52), ("MF", "MC", 50, 50), ("MF", "CM", 68, 52), ("MF", "RWB", 90, 50),
        ("FW", "ST", 38, 82), ("FW", "ST", 62, 82),
    ],
    "3-4-3": [
        ("GK", "GK", 50, 8),
        ("DF", "CB", 25, 25), ("DF", "CB", 50, 22), ("DF", "CB", 75, 25),
        ("MF", "LWB", 12, 50), ("MF", "CM", 38, 52), ("MF", "CM", 62, 52), ("MF", "RWB", 88, 50),
        ("FW", "LW", 22, 80), ("FW", "ST", 50, 84), ("FW", "RW", 78, 80),
    ],
    "5-3-2": [
        ("GK", "GK", 50, 8),
        ("DF", "LWB", 8, 32), ("DF", "CB", 28, 25), ("DF", "CB", 50, 22), ("DF", "CB", 72, 25), ("DF", "RWB", 92, 32),
        ("MF", "CM", 28, 55), ("MF", "MC", 50, 53), ("MF", "CM", 72, 55),
        ("FW", "ST", 38, 82), ("FW", "ST", 62, 82),
    ],
    "4-5-1": [
        ("GK", "GK", 50, 8),
        ("DF", "LB", 12, 28), ("DF", "CB", 38, 25), ("DF", "CB", 62, 25), ("DF", "RB", 88, 28),
        ("MF", "LM", 12, 55), ("MF", "CM", 32, 52), ("MF", "MC", 50, 50), ("MF", "CM", 68, 52), ("MF", "RM", 88, 55),
        ("FW", "ST", 50, 84),
    ],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pos_group(pos_str) -> str:
    if pd.isna(pos_str):
        return "MF"
    p = str(pos_str).upper()
    if "GK" in p: return "GK"
    if "FW" in p: return "FW"
    if "DF" in p: return "DF"
    return "MF"


def _player_pool(season: str, league_filter: str | None) -> pd.DataFrame:
    pdf = load_player_season_stats("standard", [season])
    if pdf.empty:
        return pdf
    if league_filter:
        pdf = pdf[pdf["league"] == league_filter]
    pdf = pdf.dropna(subset=["player"]).copy()
    pdf["pos_group"] = pdf["pos"].apply(_pos_group)
    pdf["display"] = pdf["player"].astype(str) + " — " + pdf["team"].astype(str)
    pdf = pdf.drop_duplicates(subset=["player", "team"]).reset_index(drop=True)
    return pdf


def _aggregate_kpis(
    starters: list[dict], subs: list[dict],
    pdf: pd.DataFrame, league_filter: str | None,
) -> None:
    rows = pdf[pdf["display"].isin([s["display"] for s in starters if s["display"]])]
    n = len(rows)

    def _sum(col: str) -> float:
        if col not in rows.columns: return 0.0
        return float(pd.to_numeric(rows[col], errors="coerce").fillna(0).sum())

    def _mean(col: str) -> float:
        if col not in rows.columns or rows.empty: return 0.0
        return float(pd.to_numeric(rows[col], errors="coerce").fillna(0).mean())

    # Valeur marchande totale (Transfermarkt)
    total_value = 0.0
    if TM_AVAILABLE:
        for r in rows.itertuples():
            tm = match_player(r.player, fbref_league=league_filter)
            if tm and pd.notna(tm.get("market_value_in_eur")):
                total_value += float(tm["market_value_in_eur"])

    kpis = [
        {"label": "Titulaires", "value": f"{n}/11",
         "color": COLORS["accent_green"] if n == 11 else COLORS["accent_gold"]},
        {"label": "Âge moyen", "value": f"{_mean('age'):.1f}", "color": COLORS["accent_blue"]},
        {"label": "Buts cumulés", "value": f"{int(_sum('Gls'))}", "color": COLORS["accent_red"]},
        {"label": "Passes D. cumulées", "value": f"{int(_sum('Ast'))}", "color": COLORS["accent_gold"]},
        {"label": "xG cumulé", "value": f"{_sum('xG'):.1f}",
         "color": COLORS["text_muted"]},
    ]
    if total_value > 0:
        kpis.insert(0, {"label": "Valeur effectif", "value": format_value(total_value),
                        "color": COLORS["accent_gold"]})
    render_kpi_row(kpis)


def _render_pitch(starters: list[dict]) -> go.Figure:
    """Terrain Plotly avec joueurs positionnés."""
    fig = go.Figure()

    pitch_green = "#0d3d1f"
    line = "#dfe7e1"

    # Pelouse
    fig.add_shape(type="rect", x0=0, y0=0, x1=100, y1=100,
                  fillcolor=pitch_green, line=dict(color=line, width=2), layer="below")
    # Ligne médiane
    fig.add_shape(type="line", x0=0, y0=50, x1=100, y1=50,
                  line=dict(color=line, width=1), layer="below")
    # Rond central
    fig.add_shape(type="circle", x0=40, y0=40, x1=60, y1=60,
                  line=dict(color=line, width=1), layer="below")
    fig.add_shape(type="circle", x0=49.3, y0=49.3, x1=50.7, y1=50.7,
                  fillcolor=line, line=dict(color=line), layer="below")
    # Surfaces
    fig.add_shape(type="rect", x0=22, y0=0,  x1=78, y1=14,
                  line=dict(color=line, width=1), layer="below")
    fig.add_shape(type="rect", x0=22, y0=86, x1=78, y1=100,
                  line=dict(color=line, width=1), layer="below")
    fig.add_shape(type="rect", x0=36, y0=0,  x1=64, y1=5,
                  line=dict(color=line, width=1), layer="below")
    fig.add_shape(type="rect", x0=36, y0=95, x1=64, y1=100,
                  line=dict(color=line, width=1), layer="below")
    # Buts
    fig.add_shape(type="rect", x0=44, y0=-2, x1=56, y1=0,
                  line=dict(color=line, width=2), layer="below")
    fig.add_shape(type="rect", x0=44, y0=100, x1=56, y1=102,
                  line=dict(color=line, width=2), layer="below")

    # Joueurs
    xs = [s["x"] for s in starters]
    ys = [s["y"] for s in starters]
    colors = [
        COLORS["accent_green"] if s["player"] else COLORS["text_muted"]
        for s in starters
    ]
    labels = []
    for s in starters:
        if s["player"]:
            short = s["player"].split()[-1] if " " in s["player"] else s["player"]
            labels.append(f"<b>{short}</b><br><span style='font-size:9px'>{s['role']}</span>")
        else:
            labels.append(f"<i>{s['role']}</i>")

    fig.add_trace(go.Scatter(
        x=xs, y=ys,
        mode="markers+text",
        marker=dict(size=26, color=colors, line=dict(color="#ffffff", width=2)),
        text=labels,
        textposition="bottom center",
        textfont=dict(color="#ffffff", size=11),
        hoverinfo="text",
        hovertext=[
            f"{s['role']} · {s['player'] or '(libre)'}"
            + (f" — {s['team']}" if s.get("team") else "")
            for s in starters
        ],
        showlegend=False,
    ))

    layout = {**PLOTLY_LAYOUT}
    layout["plot_bgcolor"] = pitch_green
    layout["margin"] = dict(l=0, r=0, t=10, b=10)
    fig.update_layout(
        **layout,
        xaxis=dict(visible=False, range=[-3, 103], fixedrange=True),
        yaxis=dict(visible=False, range=[-5, 105], fixedrange=True, scaleanchor="x"),
        height=620,
        showlegend=False,
    )
    return fig


# ── Render principal ──────────────────────────────────────────────────────────

def render(season: str, league: str) -> None:
    league_filter = None if league == "Toutes les ligues" else league
    league_label = LEAGUE_LABELS.get(league_filter, league_filter or "Big 5")

    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin-bottom:0'>🧩 Composition</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:14px'>"
        f"Crée ton XI type · {league_label} · {season}</div>",
        unsafe_allow_html=True,
    )

    # Pool de joueurs
    pdf = _player_pool(season, league_filter)
    if pdf.empty:
        st.warning("Aucun joueur disponible pour cette saison/ligue.")
        return

    # ── Barre de contrôle ─────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        formation = st.selectbox(
            "Formation", list(FORMATIONS.keys()),
            index=list(FORMATIONS.keys()).index(
                st.session_state.get("lb_formation_val", "4-3-3")
            ),
            key="lb_formation",
        )
        st.session_state["lb_formation_val"] = formation
    with c2:
        teams = ["Tous les clubs"] + sorted(pdf["team"].dropna().unique().tolist())
        team_filter = st.selectbox("Filtrer par club", teams, key="lb_team")
    with c3:
        if st.button("🗑️ Réinitialiser", use_container_width=True, key="lb_reset"):
            for k in list(st.session_state.keys()):
                if k.startswith("lb_slot_") or k.startswith("lb_sub_"):
                    del st.session_state[k]
            st.rerun()

    pool = pdf if team_filter == "Tous les clubs" else pdf[pdf["team"] == team_filter]

    slots = FORMATIONS[formation]

    # ── Sélection des 11 ──────────────────────────────────────────────────────
    pitch_col, picker_col = st.columns([3, 2], gap="large")

    starters: list[dict] = []
    used_displays: set[str] = set()

    with picker_col:
        st.markdown(
            f"<div style='font-size:0.85rem;color:{COLORS['text_muted']};"
            f"text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px'>"
            f"XI titulaire · {formation}</div>",
            unsafe_allow_html=True,
        )
        for i, (pg, role, x, y) in enumerate(slots):
            sub_pool = pool[pool["pos_group"] == pg]
            options = ["—"] + sub_pool["display"].tolist()
            current = st.session_state.get(f"lb_slot_{i}", "—")
            try:
                idx = options.index(current)
            except ValueError:
                idx = 0
            choice = st.selectbox(
                f"{role} ({pg})",
                options,
                index=idx,
                key=f"lb_slot_{i}",
            )

            if choice != "—" and choice not in used_displays:
                row = sub_pool[sub_pool["display"] == choice].iloc[0]
                starters.append({
                    "slot": i, "role": role, "pos_group": pg, "x": x, "y": y,
                    "player": row["player"], "team": row["team"],
                    "display": choice,
                })
                used_displays.add(choice)
            else:
                if choice != "—" and choice in used_displays:
                    st.warning(f"⚠️ {choice.split(' — ')[0]} déjà sélectionné.")
                starters.append({
                    "slot": i, "role": role, "pos_group": pg, "x": x, "y": y,
                    "player": None, "team": None, "display": None,
                })

    with pitch_col:
        st.plotly_chart(_render_pitch(starters), use_container_width=True)

    # ── Banc des remplaçants ──────────────────────────────────────────────────
    st.divider()
    render_section_header("Banc · 7 remplaçants", "Aucune contrainte de position.")

    sub_options = ["—"] + pool[~pool["display"].isin(used_displays)]["display"].tolist()
    sub_cols = st.columns(7)
    subs: list[dict] = []
    for i, c in enumerate(sub_cols):
        with c:
            current = st.session_state.get(f"lb_sub_{i}", "—")
            try:
                idx = sub_options.index(current)
            except ValueError:
                idx = 0
            choice = st.selectbox(
                f"S{i+1}", sub_options, index=idx,
                key=f"lb_sub_{i}",
                label_visibility="visible",
            )
            if choice != "—":
                row = pool[pool["display"] == choice].iloc[0]
                subs.append({
                    "player": row["player"], "team": row["team"],
                    "pos_group": row["pos_group"], "display": choice,
                })

    # ── Synthèse ──────────────────────────────────────────────────────────────
    st.divider()
    render_section_header("Synthèse de la composition")
    _aggregate_kpis(starters, subs, pdf, league_filter)

    # ── Tableaux récap (titulaires + bench) ───────────────────────────────────
    titles = pd.DataFrame([
        {"Rôle": s["role"], "Joueur": s["player"] or "—", "Équipe": s["team"] or "—"}
        for s in starters
    ])
    bench = pd.DataFrame([
        {"#": i + 1, "Joueur": s["player"], "Équipe": s["team"], "Position": s["pos_group"]}
        for i, s in enumerate(subs)
    ])

    cA, cB = st.columns(2)
    with cA:
        st.markdown(f"**XI · {formation}**")
        st.dataframe(titles, hide_index=True, use_container_width=True,
                     height=min(40 * len(titles) + 50, 520))
    with cB:
        st.markdown("**Banc**")
        if bench.empty:
            st.info("Aucun remplaçant sélectionné.")
        else:
            st.dataframe(bench, hide_index=True, use_container_width=True,
                         height=min(40 * len(bench) + 50, 520))
