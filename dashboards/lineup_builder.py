"""
Dashboard Composition — Tactical Board interactif.

Mode 1 : Compo équipe (auto depuis FB_lineups.csv)
  - Sélection équipe + saison → formation la plus utilisée + XI type
  - Terrain HTML/JS interactif avec drag-and-drop
  - Titulaires (vert) et remplaçants (banc ambre)

Mode 2 : Construire mon XI (manuel)
  - Sélection de la formation et des joueurs slot par slot
  - Mêmes fonctionnalités qu'avant
"""
from __future__ import annotations

import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go

from config import COLORS, LEAGUE_LABELS, PLOTLY_LAYOUT
from components.kpi_cards import render_kpi_row, render_section_header
from data.loader import load_player_season_stats
from data.processor import get_typical_lineup, formation_coords, get_squad_with_positions, squad_pos_to_xy

try:
    from transfermarkt.matcher import (
        match_player, get_club_logo, format_value,
        enrich_with_photos,
    )
    TM_AVAILABLE = True
except Exception:
    TM_AVAILABLE = False
    def match_player(*a, **kw): return None
    def get_club_logo(*a, **kw): return None
    def format_value(v): return "—"
    def enrich_with_photos(df, *a, **kw): return df


# ── Formations (pour le mode manuel) ──────────────────────────────────────────

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
        ("MF", "LWB", 10, 50), ("MF", "CM", 32, 52), ("MF", "MC", 50, 50),
        ("MF", "CM", 68, 52), ("MF", "RWB", 90, 50),
        ("FW", "ST", 38, 82), ("FW", "ST", 62, 82),
    ],
    "3-4-3": [
        ("GK", "GK", 50, 8),
        ("DF", "CB", 25, 25), ("DF", "CB", 50, 22), ("DF", "CB", 75, 25),
        ("MF", "LWB", 12, 50), ("MF", "CM", 38, 52),
        ("MF", "CM", 62, 52), ("MF", "RWB", 88, 50),
        ("FW", "LW", 22, 80), ("FW", "ST", 50, 84), ("FW", "RW", 78, 80),
    ],
    "5-3-2": [
        ("GK", "GK", 50, 8),
        ("DF", "LWB", 8, 32), ("DF", "CB", 28, 25), ("DF", "CB", 50, 22),
        ("DF", "CB", 72, 25), ("DF", "RWB", 92, 32),
        ("MF", "CM", 28, 55), ("MF", "MC", 50, 53), ("MF", "CM", 72, 55),
        ("FW", "ST", 38, 82), ("FW", "ST", 62, 82),
    ],
    "4-5-1": [
        ("GK", "GK", 50, 8),
        ("DF", "LB", 12, 28), ("DF", "CB", 38, 25), ("DF", "CB", 62, 25), ("DF", "RB", 88, 28),
        ("MF", "LM", 12, 55), ("MF", "CM", 32, 52), ("MF", "MC", 50, 50),
        ("MF", "CM", 68, 52), ("MF", "RM", 88, 55),
        ("FW", "ST", 50, 84),
    ],
}


# ── HTML Tactical Board ───────────────────────────────────────────────────────

def _build_tactical_html(
    starters: list[dict],
    subs: list[dict],
    formation: str,
    team_name: str,
    total_games: int,
) -> str:
    """Génère le HTML complet du tableau tactique interactif."""

    # Assign coordinates to starters
    coords = formation_coords(formation)
    # Group coords by position group
    coords_by_group: dict[str, list[dict]] = {}
    for pg, x, y in coords:
        if pg not in coords_by_group:
            coords_by_group[pg] = []
        coords_by_group[pg].append({"x": x, "y": y})

    idx_by_group: dict[str, int] = {"GK": 0, "DF": 0, "MF": 0, "FW": 0}
    starters_data = []
    for s in starters:
        pg = s["pos_group"]
        grp = coords_by_group.get(pg, [])
        gi = idx_by_group.get(pg, 0)
        if gi < len(grp):
            coord = grp[gi]
            idx_by_group[pg] = gi + 1
        else:
            coord = {"x": 50.0, "y": 50.0}
        short = s["player"].split()[-1] if " " in s["player"] else s["player"]
        pct = round(s["apps"] / max(total_games, 1) * 100)
        starters_data.append({
            **s,
            "x_pct": coord["x"],
            "y_pct": coord["y"],
            "short": short,
            "pct": pct,
            "photo_url": s.get("photo_url", ""),
        })

    subs_data = []
    for s in subs:
        short = s["player"].split()[-1] if " " in s["player"] else s["player"]
        pct = round(s["apps"] / max(total_games, 1) * 100)
        subs_data.append({
            **s,
            "short": short,
            "pct": pct,
            "photo_url": s.get("photo_url", ""),
        })

    players_json = json.dumps({
        "starters": starters_data,
        "subs": subs_data,
        "formation": formation,
        "total_games": total_games,
        "team": team_name,
    }, ensure_ascii=False)

    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{
  background:#0c0c18;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Arial,sans-serif;
  color:#fff;
  user-select:none;
  -webkit-user-select:none;
  overscroll-behavior:none;
}
#board{padding:8px 10px 10px}
#header{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:8px;
}
#team-name{font-size:13px;font-weight:700;color:rgba(255,255,255,.7);letter-spacing:.05em;text-transform:uppercase}
#stats-badge{
  background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);
  border-radius:20px;padding:3px 10px;font-size:11px;color:rgba(255,255,255,.6)
}
#pitch-wrapper{
  position:relative;
  width:100%;
  height:580px;
  background:linear-gradient(180deg,#0d4a12 0%,#145c18 45%,#145c18 55%,#0d4a12 100%);
  border:2px solid rgba(255,255,255,.55);
  border-radius:10px;
  overflow:hidden;
  box-shadow:0 4px 30px rgba(0,0,0,.5);
}
#pitch-svg{
  position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;
}
#formation-badge{
  position:absolute;top:8px;left:50%;transform:translateX(-50%);
  background:rgba(0,0,0,.65);border:1px solid rgba(255,255,255,.25);
  border-radius:5px;padding:3px 14px;
  font-size:14px;font-weight:800;letter-spacing:.08em;z-index:100;
  backdrop-filter:blur(4px);
}
#legend{
  position:absolute;bottom:8px;right:8px;
  display:flex;gap:10px;z-index:100;
}
.leg-item{display:flex;align-items:center;gap:4px;font-size:9.5px;color:rgba(255,255,255,.65)}
.leg-dot{width:11px;height:11px;border-radius:50%;border:1.5px solid rgba(255,255,255,.7)}

.p-token{
  position:absolute;
  width:52px;height:52px;
  border-radius:50%;
  border:2.5px solid rgba(255,255,255,.85);
  display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  cursor:grab;
  transform:translate(-50%,-50%);
  font-size:10px;font-weight:700;
  text-align:center;overflow:hidden;
  background:#22c55e;
  box-shadow:0 2px 10px rgba(0,0,0,.45);
  z-index:10;
  touch-action:none;
  transition:box-shadow .12s;
}
.p-token:active{cursor:grabbing;box-shadow:0 4px 20px rgba(255,255,255,.35);z-index:1000}
.p-token .p-num{
  font-size:13px;font-weight:900;line-height:1;
  text-shadow:0 1px 3px rgba(0,0,0,.6);
}
.p-token img{
  width:100%;height:100%;object-fit:cover;
  position:absolute;top:0;left:0;border-radius:50%;
}
.p-token .p-badge{
  position:absolute;bottom:1px;right:1px;
  background:rgba(0,0,0,.75);border-radius:50%;
  width:17px;height:17px;
  display:flex;align-items:center;justify-content:center;
  font-size:9px;font-weight:800;line-height:1;
  border:1px solid rgba(255,255,255,.5);
}
.p-label{
  position:absolute;
  transform:translateX(-50%);
  pointer-events:none;
  white-space:nowrap;
  font-size:9px;font-weight:700;
  color:#fff;
  text-shadow:0 1px 4px rgba(0,0,0,1),0 0 6px rgba(0,0,0,.9);
  letter-spacing:.02em;
}
/* Bench */
#bench{
  margin-top:10px;
  background:rgba(0,0,0,.35);
  border:1px solid rgba(255,255,255,.08);
  border-radius:8px;padding:10px 12px 12px;
}
#bench-title{
  font-size:10px;text-transform:uppercase;letter-spacing:.1em;
  color:rgba(255,255,255,.4);margin-bottom:8px;font-weight:600;
}
#bench-players{display:flex;gap:7px;flex-wrap:wrap}
.bp{
  display:flex;align-items:center;gap:6px;
  background:rgba(245,158,11,.12);
  border:1px solid rgba(245,158,11,.3);
  border-radius:20px;padding:5px 10px 5px 5px;
  font-size:11px;cursor:default;
}
.bp:hover{background:rgba(245,158,11,.2)}
.bp-av{
  width:30px;height:30px;border-radius:50%;
  background:#f59e0b;
  display:flex;align-items:center;justify-content:center;
  font-weight:800;font-size:10px;overflow:hidden;flex-shrink:0;
}
.bp-av img{width:100%;height:100%;object-fit:cover;border-radius:50%}
.bp-name{font-weight:600;font-size:11px;line-height:1.1}
.bp-pos{font-size:9px;color:rgba(255,255,255,.45);margin-top:1px}
/* Info bar */
#info-bar{
  margin-top:8px;display:flex;gap:10px;flex-wrap:wrap;
}
.info-chip{
  background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
  border-radius:6px;padding:4px 10px;font-size:10.5px;color:rgba(255,255,255,.6);
}
.info-chip span{color:#fff;font-weight:700}
</style>
</head>
<body>
<div id="board">
  <div id="header">
    <div id="team-name"></div>
    <div id="stats-badge"></div>
  </div>
  <div id="pitch-wrapper">
    <svg id="pitch-svg" viewBox="0 0 100 100" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="4" y="2" width="92" height="96" fill="none" stroke="rgba(255,255,255,.7)" stroke-width=".5"/>
      <line x1="4" y1="50" x2="96" y2="50" stroke="rgba(255,255,255,.7)" stroke-width=".35"/>
      <circle cx="50" cy="50" r="11.5" fill="none" stroke="rgba(255,255,255,.7)" stroke-width=".35"/>
      <circle cx="50" cy="50" r=".8" fill="rgba(255,255,255,.8)"/>
      <rect x="22" y="2" width="56" height="19" fill="none" stroke="rgba(255,255,255,.65)" stroke-width=".35"/>
      <rect x="36" y="2" width="28" height="7" fill="none" stroke="rgba(255,255,255,.6)" stroke-width=".3"/>
      <rect x="43" y=".3" width="14" height="2" fill="none" stroke="rgba(255,255,255,.8)" stroke-width=".5"/>
      <rect x="22" y="79" width="56" height="19" fill="none" stroke="rgba(255,255,255,.65)" stroke-width=".35"/>
      <rect x="36" y="91" width="28" height="7" fill="none" stroke="rgba(255,255,255,.6)" stroke-width=".3"/>
      <rect x="43" y="97.7" width="14" height="2" fill="none" stroke="rgba(255,255,255,.8)" stroke-width=".5"/>
      <circle cx="50" cy="14.5" r=".7" fill="rgba(255,255,255,.7)"/>
      <circle cx="50" cy="85.5" r=".7" fill="rgba(255,255,255,.7)"/>
      <path d="M4,5.5 A3.5,3.5 0 0,1 7.5,2" fill="none" stroke="rgba(255,255,255,.5)" stroke-width=".3"/>
      <path d="M92.5,2 A3.5,3.5 0 0,1 96,5.5" fill="none" stroke="rgba(255,255,255,.5)" stroke-width=".3"/>
      <path d="M4,94.5 A3.5,3.5 0 0,0 7.5,98" fill="none" stroke="rgba(255,255,255,.5)" stroke-width=".3"/>
      <path d="M92.5,98 A3.5,3.5 0 0,0 96,94.5" fill="none" stroke="rgba(255,255,255,.5)" stroke-width=".3"/>
    </svg>
    <div id="formation-badge"></div>
    <div id="legend">
      <div class="leg-item"><div class="leg-dot" style="background:#22c55e"></div>Titulaire</div>
      <div class="leg-item"><div class="leg-dot" style="background:#f59e0b"></div>Remplaçant</div>
    </div>
  </div>
  <div id="bench">
    <div id="bench-title">Banc des remplaçants</div>
    <div id="bench-players"></div>
  </div>
  <div id="info-bar"></div>
</div>

<script>
const DATA = """ + players_json + """;
const pitch = document.getElementById('pitch-wrapper');
const fBadge = document.getElementById('formation-badge');
const benchDiv = document.getElementById('bench-players');
const infoBar = document.getElementById('info-bar');
const teamNameEl = document.getElementById('team-name');
const statsBadge = document.getElementById('stats-badge');

teamNameEl.textContent = DATA.team;
fBadge.textContent = DATA.formation;
statsBadge.textContent = DATA.total_games + ' match' + (DATA.total_games > 1 ? 's' : '') + ' analysés';

function shortName(name) {
  const parts = name.split(' ');
  return parts.length > 1 ? parts[parts.length - 1] : parts[0];
}

function makeDraggable(token, label) {
  let dragging = false, ox, oy, otl, ott;
  const start = (e) => {
    dragging = true;
    const pt = e.touches ? e.touches[0] : e;
    ox = pt.clientX; oy = pt.clientY;
    otl = parseFloat(token.style.left);
    ott = parseFloat(token.style.top);
    token.style.zIndex = 1000;
    e.preventDefault();
  };
  const move = (e) => {
    if (!dragging) return;
    const pt = e.touches ? e.touches[0] : e;
    const rect = pitch.getBoundingClientRect();
    const nx = Math.max(3, Math.min(97, otl + (pt.clientX - ox) / rect.width * 100));
    const ny = Math.max(3, Math.min(97, ott + (pt.clientY - oy) / rect.height * 100));
    token.style.left = nx + '%';
    token.style.top = ny + '%';
    if (label) {
      label.style.left = nx + '%';
      label.style.top = 'calc(' + ny + '% + 31px)';
    }
    e.preventDefault();
  };
  const end = () => { dragging = false; token.style.zIndex = 10; };
  token.addEventListener('mousedown', start);
  token.addEventListener('touchstart', start, {passive:false});
  document.addEventListener('mousemove', move);
  document.addEventListener('touchmove', move, {passive:false});
  document.addEventListener('mouseup', end);
  document.addEventListener('touchend', end);
}

DATA.starters.forEach((p, i) => {
  const token = document.createElement('div');
  token.className = 'p-token';
  token.style.left = p.x_pct + '%';
  token.style.top = p.y_pct + '%';

  if (p.photo_url) {
    token.innerHTML = '<img src="' + p.photo_url + '" alt="" onerror="this.style.display=\'none\'">'
      + '<span class="p-badge">' + (p.jersey_number || '') + '</span>';
  } else {
    token.innerHTML = '<span class="p-num">' + (p.jersey_number || p.short[0]) + '</span>';
  }
  token.title = p.player + ' · ' + p.primary_pos + ' · ' + p.apps + ' matchs (' + p.pct + '%)';
  pitch.appendChild(token);

  const label = document.createElement('div');
  label.className = 'p-label';
  label.style.left = p.x_pct + '%';
  label.style.top = 'calc(' + p.y_pct + '% + 31px)';
  label.textContent = p.short;
  pitch.appendChild(label);

  makeDraggable(token, label);
});

DATA.subs.forEach((p) => {
  const item = document.createElement('div');
  item.className = 'bp';
  item.title = p.player + ' · ' + p.primary_pos;
  let avContent = '';
  if (p.photo_url) {
    avContent = '<img src="' + p.photo_url + '" alt="" onerror="this.outerHTML=\'<span>' + (p.jersey_number || p.short[0]) + '</span>\'">';
  } else {
    avContent = '<span>' + (p.jersey_number || p.short[0]) + '</span>';
  }
  item.innerHTML = '<div class="bp-av">' + avContent + '</div>'
    + '<div><div class="bp-name">' + p.short + '</div>'
    + '<div class="bp-pos">' + p.primary_pos + ' · ' + p.apps + 'M</div></div>';
  benchDiv.appendChild(item);
});

// Info bar
const chips = [
  {label: 'Formation type', val: DATA.formation},
  {label: 'Matchs', val: DATA.total_games},
  {label: 'Titulaires sélectionnés', val: DATA.starters.length + '/11'},
];
chips.forEach(c => {
  const chip = document.createElement('div');
  chip.className = 'info-chip';
  chip.innerHTML = c.label + ' : <span>' + c.val + '</span>';
  infoBar.appendChild(chip);
});
</script>
</body>
</html>"""
    return html


# ── Helpers mode manuel ────────────────────────────────────────────────────────

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


def _aggregate_kpis(starters: list[dict], pdf: pd.DataFrame, league_filter) -> None:
    rows = pdf[pdf["display"].isin([s["display"] for s in starters if s["display"]])]
    def _sum(col):
        if col not in rows.columns: return 0.0
        return float(pd.to_numeric(rows[col], errors="coerce").fillna(0).sum())
    def _mean(col):
        if col not in rows.columns or rows.empty: return 0.0
        return float(pd.to_numeric(rows[col], errors="coerce").fillna(0).mean())

    total_value = 0.0
    if TM_AVAILABLE:
        for r in rows.itertuples():
            tm = match_player(r.player, fbref_league=league_filter)
            if tm and pd.notna(tm.get("market_value_in_eur")):
                total_value += float(tm["market_value_in_eur"])

    kpis = [
        {"label": "Titulaires", "value": f"{len(rows)}/11",
         "color": COLORS["accent_green"] if len(rows) == 11 else COLORS["accent_gold"]},
        {"label": "Âge moyen", "value": f"{_mean('age'):.1f}", "color": COLORS["accent_blue"]},
        {"label": "Buts cumulés", "value": f"{int(_sum('Gls'))}", "color": COLORS["accent_red"]},
        {"label": "Passes D.", "value": f"{int(_sum('Ast'))}", "color": COLORS["accent_gold"]},
        {"label": "xG cumulé", "value": f"{_sum('xG'):.1f}", "color": COLORS["text_muted"]},
    ]
    if total_value > 0:
        kpis.insert(0, {"label": "Valeur effectif", "value": format_value(total_value),
                        "color": COLORS["accent_gold"]})
    render_kpi_row(kpis)


def _render_manual_pitch(starters: list[dict]) -> go.Figure:
    """Terrain Plotly pour le mode manuel."""
    fig = go.Figure()
    pitch_green = "#0d3d1f"
    line = "#dfe7e1"
    fig.add_shape(type="rect", x0=0, y0=0, x1=100, y1=100,
                  fillcolor=pitch_green, line=dict(color=line, width=2), layer="below")
    fig.add_shape(type="line", x0=0, y0=50, x1=100, y1=50,
                  line=dict(color=line, width=1), layer="below")
    fig.add_shape(type="circle", x0=40, y0=40, x1=60, y1=60,
                  line=dict(color=line, width=1), layer="below")
    for x0, y0, x1, y1 in [(22,0,78,14),(22,86,78,100),(36,0,64,5),(36,95,64,100)]:
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                      line=dict(color=line, width=1), layer="below")
    for x0, y0, x1, y1 in [(44,-2,56,0),(44,100,56,102)]:
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                      line=dict(color=line, width=2), layer="below")

    xs = [s["x"] for s in starters]
    ys = [s["y"] for s in starters]
    colors = [COLORS["accent_green"] if s["player"] else COLORS["text_muted"] for s in starters]
    labels = []
    for s in starters:
        if s["player"]:
            short = s["player"].split()[-1] if " " in s["player"] else s["player"]
            labels.append(f"<b>{short}</b><br><span style='font-size:9px'>{s['role']}</span>")
        else:
            labels.append(f"<i>{s['role']}</i>")

    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text",
        marker=dict(size=26, color=colors, line=dict(color="#ffffff", width=2)),
        text=labels, textposition="bottom center",
        textfont=dict(color="#ffffff", size=11),
        hoverinfo="text",
        hovertext=[
            f"{s['role']} · {s['player'] or '(libre)'}"
            + (f" — {s['team']}" if s.get('team') else "")
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
        height=620, showlegend=False,
    )
    return fig


# ── Render principal ──────────────────────────────────────────────────────────

def render(season: str, league: str) -> None:
    league_filter = None if league == "Toutes les ligues" else league
    league_label = LEAGUE_LABELS.get(league_filter, league_filter or "Big 5")

    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin-bottom:0'>🧩 Composition</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:14px'>"
        f"Tableau tactique interactif · {league_label} · {season}</div>",
        unsafe_allow_html=True,
    )

    mode = st.radio(
        "Mode",
        ["🔍 Compo équipe (auto)", "🛠️ Construire mon XI"],
        horizontal=True,
        label_visibility="collapsed",
        key="lb_mode",
    )

    if mode.startswith("🔍"):
        _render_auto_board(season, league_filter, league_label)
    else:
        _render_manual_builder(season, league_filter, league_label)


# ── Palette couleurs selon les apparitions ────────────────────────────────────

def _token_color(appearances: int) -> str:
    """
    Couleur du token selon le nombre de matchs joués à ce poste.
    Purple = le plus de minutes (≥ 5 apps), jaune = rotationnel, sombre = rare.
    """
    if appearances >= 10:
        return "#16a34a"   # vert — joueur clé / très régulier
    if appearances >= 5:
        return "#9333ea"   # violet — titulaire régulier
    if appearances >= 3:
        return "#f59e0b"   # jaune — rotationnel
    return "#1f2937"       # sombre — peu apparu


# ── Builder HTML terrain horizontal (Map.png) ─────────────────────────────────

def _build_squad_html(
    squad_df: "pd.DataFrame",
    team_name: str,
    photo_map: dict,
) -> str:
    """
    Génère le HTML du terrain horizontal (SVG pur) avec tous les joueurs (≥200 min).
    Terrain : rectangle vert avec lignes blanches SVG.
    Tokens : cercles colorés selon les minutes jouées, nom en dessous.
    """
    import json as _json

    tokens = []
    for _, row in squad_df.iterrows():
        tokens.append({
            "player":      str(row["player"]),
            "short":       str(row["player"]).split()[-1],
            "pos":         str(row["pos"]),
            "appearances": int(row["appearances"]),
            "minutes":     int(row.get("minutes", 0)),
            "color":       _token_color(int(row["appearances"])),
            "x_pct":       float(row["x_pct"]),
            "y_pct":       float(row["y_pct"]),
            "photo_url":   photo_map.get(str(row["player"]), ""),
        })

    tokens_json = _json.dumps(tokens, ensure_ascii=False)
    team_js    = team_name.replace("'", "\\'")

    # ── Terrain SVG horizontal ────────────────────────────────────────────────
    # ViewBox 105×68 (dimensions FIFA en mètres — proportions réalistes)
    # Rendu dans un <div> 100% × 540px
    PITCH_SVG = (
        "<svg id='pitch-svg' viewBox='0 0 105 68' "
        "preserveAspectRatio='none' "
        "xmlns='http://www.w3.org/2000/svg' "
        "style='position:absolute;top:0;left:0;width:100%;height:100%;'>"

        # Fond vert alterné (bandes)
        "<defs>"
        "<pattern id='stripes' x='0' y='0' width='10.5' height='68' patternUnits='userSpaceOnUse'>"
        "<rect x='0' y='0' width='5.25' height='68' fill='#2d7a3a'/>"
        "<rect x='5.25' y='0' width='5.25' height='68' fill='#2f8340'/>"
        "</pattern>"
        "</defs>"
        "<rect x='0' y='0' width='105' height='68' fill='url(#stripes)'/>"

        # Bordure du terrain
        "<rect x='2' y='2' width='101' height='64' fill='none' "
        "stroke='rgba(255,255,255,0.85)' stroke-width='0.5'/>"

        # Ligne médiane
        "<line x1='52.5' y1='2' x2='52.5' y2='66' "
        "stroke='rgba(255,255,255,0.85)' stroke-width='0.4'/>"

        # Cercle central
        "<circle cx='52.5' cy='34' r='9.15' fill='none' "
        "stroke='rgba(255,255,255,0.85)' stroke-width='0.4'/>"
        "<circle cx='52.5' cy='34' r='0.5' fill='rgba(255,255,255,0.9)'/>"

        # Surface de réparation gauche (16.5m × 40.32m)
        "<rect x='2' y='13.84' width='16.5' height='40.32' fill='none' "
        "stroke='rgba(255,255,255,0.8)' stroke-width='0.4'/>"
        # Surface de but gauche
        "<rect x='2' y='24.84' width='5.5' height='18.32' fill='none' "
        "stroke='rgba(255,255,255,0.7)' stroke-width='0.35'/>"
        # But gauche
        "<rect x='0' y='29.34' width='2' height='9.32' fill='none' "
        "stroke='rgba(255,255,255,0.9)' stroke-width='0.6'/>"
        # Arc surface gauche
        "<path d='M 18.5 26.5 A 9.15 9.15 0 0 1 18.5 41.5' fill='none' "
        "stroke='rgba(255,255,255,0.7)' stroke-width='0.35'/>"
        # Point de penalty gauche
        "<circle cx='11' cy='34' r='0.45' fill='rgba(255,255,255,0.85)'/>"

        # Surface de réparation droite
        "<rect x='86.5' y='13.84' width='16.5' height='40.32' fill='none' "
        "stroke='rgba(255,255,255,0.8)' stroke-width='0.4'/>"
        # Surface de but droite
        "<rect x='97.5' y='24.84' width='5.5' height='18.32' fill='none' "
        "stroke='rgba(255,255,255,0.7)' stroke-width='0.35'/>"
        # But droit
        "<rect x='103' y='29.34' width='2' height='9.32' fill='none' "
        "stroke='rgba(255,255,255,0.9)' stroke-width='0.6'/>"
        # Arc surface droite
        "<path d='M 86.5 26.5 A 9.15 9.15 0 0 0 86.5 41.5' fill='none' "
        "stroke='rgba(255,255,255,0.7)' stroke-width='0.35'/>"
        # Point de penalty droit
        "<circle cx='94' cy='34' r='0.45' fill='rgba(255,255,255,0.85)'/>"

        # Arcs de coin
        "<path d='M 2 4.5 A 1.5 1.5 0 0 0 4.5 2' fill='none' stroke='rgba(255,255,255,0.6)' stroke-width='0.35'/>"
        "<path d='M 100.5 2 A 1.5 1.5 0 0 0 103 4.5' fill='none' stroke='rgba(255,255,255,0.6)' stroke-width='0.35'/>"
        "<path d='M 2 63.5 A 1.5 1.5 0 0 1 4.5 66' fill='none' stroke='rgba(255,255,255,0.6)' stroke-width='0.35'/>"
        "<path d='M 100.5 66 A 1.5 1.5 0 0 1 103 63.5' fill='none' stroke='rgba(255,255,255,0.6)' stroke-width='0.35'/>"

        "</svg>"
    )

    html = (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        "<style>"
        "*{box-sizing:border-box;margin:0;padding:0}"
        "body{background:#111827;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;"
        "color:#fff;user-select:none;-webkit-user-select:none;overscroll-behavior:none}"
        "#board{padding:8px 10px}"
        "#header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;flex-wrap:wrap;gap:6px}"
        "#team-name{font-size:13px;font-weight:700;color:rgba(255,255,255,.65);letter-spacing:.07em;text-transform:uppercase}"
        "#legend{display:flex;gap:14px;flex-wrap:wrap}"
        ".leg{display:flex;align-items:center;gap:5px;font-size:10px;color:rgba(255,255,255,.5)}"
        ".leg-dot{width:12px;height:12px;border-radius:50%;border:2px solid rgba(255,255,255,.55)}"
        "#pitch-wrap{"
        "position:relative;width:100%;height:520px;"
        "border-radius:6px;overflow:hidden;"
        "box-shadow:0 2px 20px rgba(0,0,0,.55)}"
        ".tok{"
        "position:absolute;width:38px;height:38px;border-radius:50%;"
        "border:3.5px solid white;"
        "display:flex;align-items:center;justify-content:center;"
        "cursor:grab;transform:translate(-50%,-50%);"
        "font-size:11px;font-weight:800;overflow:hidden;"
        "box-shadow:0 2px 10px rgba(0,0,0,.6);"
        "z-index:10;touch-action:none;"
        "text-shadow:0 1px 3px rgba(0,0,0,.8)}"
        ".tok:active{cursor:grabbing;z-index:1000;"
        "box-shadow:0 4px 18px rgba(0,0,0,.7)}"
        ".tok img{width:100%;height:100%;object-fit:cover;position:absolute;border-radius:50%}"
        ".tok .ab{"
        "position:absolute;bottom:-1px;right:-1px;"
        "width:15px;height:15px;border-radius:50%;"
        "background:rgba(0,0,0,.9);border:1.5px solid rgba(255,255,255,.6);"
        "font-size:8px;font-weight:800;display:flex;align-items:center;justify-content:center;"
        "color:#fff}"
        ".lbl{"
        "position:absolute;transform:translateX(-50%);"
        "pointer-events:none;white-space:nowrap;"
        "font-size:9.5px;font-weight:700;color:#fff;"
        "text-shadow:0 1px 5px #000,0 0 8px #000;"
        "letter-spacing:.01em;line-height:1}"
        "</style></head><body>"
        "<div id='board'>"
        "<div id='header'>"
        "<div id='team-name'></div>"
        "<div id='legend'>"
        "<div class='leg'><div class='leg-dot' style='background:#16a34a'></div>10+ matchs</div>"
        "<div class='leg'><div class='leg-dot' style='background:#9333ea'></div>5–9 matchs</div>"
        "<div class='leg'><div class='leg-dot' style='background:#f59e0b'></div>3–4 matchs</div>"
        "<div class='leg'><div class='leg-dot' style='background:#374151'></div>1–2 matchs</div>"
        "</div></div>"
        "<div id='pitch-wrap'>"
        + PITCH_SVG +
        "</div>"
        "</div>"
        "<script>"
        "const T=" + tokens_json + ";"
        "document.getElementById('team-name').textContent='" + team_js + "';"
        "const W=document.getElementById('pitch-wrap');"
        "function drag(tok,lbl){"
        "let dr=0,ox,oy,sl,st;"
        "function dn(e){dr=1;"
        "const p=e.touches?e.touches[0]:e;"
        "ox=p.clientX;oy=p.clientY;"
        "sl=parseFloat(tok.style.left);st=parseFloat(tok.style.top);"
        "tok.style.zIndex=999;e.preventDefault();}"
        "function mv(e){if(!dr)return;"
        "const p=e.touches?e.touches[0]:e;"
        "const r=W.getBoundingClientRect();"
        "const nx=Math.max(1,Math.min(99,sl+(p.clientX-ox)/r.width*100));"
        "const ny=Math.max(1,Math.min(99,st+(p.clientY-oy)/r.height*100));"
        "tok.style.left=nx+'%';tok.style.top=ny+'%';"
        "lbl.style.left=nx+'%';lbl.style.top='calc('+ny+'% + 21px)';"
        "e.preventDefault();}"
        "function up(){dr=0;tok.style.zIndex=10;}"
        "tok.addEventListener('mousedown',dn);"
        "tok.addEventListener('touchstart',dn,{passive:false});"
        "document.addEventListener('mousemove',mv);"
        "document.addEventListener('touchmove',mv,{passive:false});"
        "document.addEventListener('mouseup',up);"
        "document.addEventListener('touchend',up);}"
        "T.forEach(p=>{"
        "const t=document.createElement('div');"
        "t.className='tok';"
        "t.style.left=p.x_pct+'%';"
        "t.style.top=p.y_pct+'%';"
        "t.style.background=p.color;"
        "t.style.border='3.5px solid '+p.color;"
        "t.style.boxShadow='0 0 0 2px rgba(255,255,255,.75),0 2px 10px rgba(0,0,0,.6)';"
        "if(p.photo_url){"
        "const img=document.createElement('img');"
        "img.src=p.photo_url;"
        "img.onerror=()=>img.remove();"
        "t.appendChild(img);"
        "const b=document.createElement('div');"
        "b.className='ab';b.textContent=p.appearances;"
        "t.appendChild(b);"
        "}else{"
        "t.textContent=p.appearances;"
        "}"
        "t.title=p.player+' · '+p.pos+' · '+p.appearances+' match(s) · '+p.minutes+' min';"
        "W.appendChild(t);"
        "const l=document.createElement('div');"
        "l.className='lbl';"
        "l.style.cssText='left:'+p.x_pct+'%;top:calc('+p.y_pct+'% + 21px);';"
        "l.textContent=p.short;"
        "W.appendChild(l);"
        "drag(t,l);"
        "});"
        "</script></body></html>"
    )
    return html


# ── Mode Auto ─────────────────────────────────────────────────────────────────

def _render_auto_board(
    season: str, league_filter: str | None, league_label: str,
) -> None:
    from components.filters import select_team
    from components.kpi_cards import render_section_header

    team = select_team(season, league_filter or "Toutes les ligues",
                       label="Équipe à analyser", key="tb_team",
                       show_preview=False)
    if not team:
        return

    # Logo + header
    logo_url = get_club_logo(team, league_filter)
    if logo_url:
        c1, c2 = st.columns([1, 9])
        with c1:
            st.image(logo_url, width=60)
        with c2:
            c_text = COLORS["text"]
            c_muted = COLORS["text_muted"]
            st.markdown(
                "<div style='padding:4px 0'>"
                "<span style='font-size:1.3rem;font-weight:800;color:" + c_text + "'>" + team + "</span>"
                "<div style='font-size:0.8rem;color:" + c_muted + "'>" + league_label + " · " + season + "</div>"
                "</div>",
                unsafe_allow_html=True,
            )
    else:
        c_text = COLORS["text"]
        c_muted = COLORS["text_muted"]
        st.markdown(
            "<span style='font-size:1.3rem;font-weight:800;color:" + c_text + "'>🏟️ " + team + "</span>"
            "<span style='font-size:0.8rem;color:" + c_muted + ";margin-left:8px'>"
            + league_label + " · " + season + "</span>",
            unsafe_allow_html=True,
        )

    st.divider()

    with st.spinner("Chargement de l'effectif…"):
        squad_df = get_squad_with_positions(team, season, league_filter)

    if squad_df.empty:
        st.warning(
            "Pas de données de composition pour cette équipe / saison. "
            "Vérifiez que le fichier FB_lineups.csv est disponible."
        )
        return

    # Assigner les coordonnées (x%, y%) à chaque joueur
    pos_indices: dict[str, int] = {}
    pos_totals: dict[str, int] = squad_df.groupby("pos").size().to_dict()
    xs, ys = [], []
    for _, row in squad_df.iterrows():
        pos = str(row["pos"])
        idx = pos_indices.get(pos, 0)
        pos_indices[pos] = idx + 1
        total = pos_totals.get(pos, 1)
        x, y = squad_pos_to_xy(pos, idx, total)
        xs.append(x)
        ys.append(y)
    squad_df = squad_df.copy()
    squad_df["x_pct"] = xs
    squad_df["y_pct"] = ys

    # Enrichissement TM (photos)
    photo_map: dict[str, str] = {}
    if TM_AVAILABLE:
        try:
            enr = enrich_with_photos(
                squad_df[["player"]].copy(),
                player_col="player",
                league=league_filter,
            )
            if "image_url" in enr.columns:
                for _, r in enr.iterrows():
                    url = r.get("image_url", "")
                    if url and isinstance(url, str):
                        photo_map[r["player"]] = url
        except Exception:
            pass

    # KPI row
    n_players = len(squad_df)
    n_regular  = int((squad_df["appearances"] >= 5).sum())
    avg_apps   = round(squad_df["appearances"].mean(), 1)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Joueurs de l'effectif", n_players)
    with c2:
        st.metric("Titulaires réguliers (≥5 matchs)", n_regular)
    with c3:
        st.metric("Moy. matchs / joueur", avg_apps)

    # Tableau tactique HTML
    html = _build_squad_html(squad_df, team, photo_map)
    components.html(html, height=590, scrolling=False)

    # Table récapitulative
    with st.expander("📋 Effectif complet"):
        disp = squad_df[["player", "pos", "pos_group", "appearances", "jersey"]].rename(columns={
            "player": "Joueur", "pos": "Poste", "pos_group": "Groupe",
            "appearances": "Matchs", "jersey": "N°",
        })
        st.dataframe(disp, hide_index=True, use_container_width=True,
                     height=min(36 * len(disp) + 40, 600))


# ── Mode Manuel ───────────────────────────────────────────────────────────────

def _render_manual_builder(
    season: str, league_filter: str | None, league_label: str,
) -> None:
    pdf = _player_pool(season, league_filter)
    if pdf.empty:
        st.warning("Aucun joueur disponible pour cette saison/ligue.")
        return

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
                f"{role} ({pg})", options, index=idx, key=f"lb_slot_{i}",
            )
            if choice != "—" and choice not in used_displays:
                row = sub_pool[sub_pool["display"] == choice].iloc[0]
                starters.append({
                    "slot": i, "role": role, "pos_group": pg, "x": x, "y": y,
                    "player": row["player"], "team": row["team"], "display": choice,
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
        st.plotly_chart(_render_manual_pitch(starters), use_container_width=True)

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
                f"S{i+1}", sub_options, index=idx, key=f"lb_sub_{i}",
            )
            if choice != "—":
                row = pool[pool["display"] == choice].iloc[0]
                subs.append({
                    "player": row["player"], "team": row["team"],
                    "pos_group": row["pos_group"], "display": choice,
                })

    st.divider()
    render_section_header("Synthèse de la composition")
    _aggregate_kpis(starters, pdf, league_filter)

    titres = pd.DataFrame([
        {"Rôle": s["role"], "Joueur": s["player"] or "—", "Équipe": s["team"] or "—"}
        for s in starters
    ])
    bench_df = pd.DataFrame([
        {"#": i + 1, "Joueur": s["player"], "Équipe": s["team"], "Position": s["pos_group"]}
        for i, s in enumerate(subs)
    ])
    cA, cB = st.columns(2)
    with cA:
        st.markdown(f"**XI · {formation}**")
        st.dataframe(titres, hide_index=True, use_container_width=True,
                     height=min(40 * len(titres) + 50, 520))
    with cB:
        st.markdown("**Banc**")
        if bench_df.empty:
            st.info("Aucun remplaçant sélectionné.")
        else:
            st.dataframe(bench_df, hide_index=True, use_container_width=True,
                         height=min(40 * len(bench_df) + 50, 520))
