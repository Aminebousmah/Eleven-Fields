"""
ElevenField — Composants de design (refonte v2).

Helpers HTML produisant des chaînes prêtes à injecter via
st.markdown(unsafe_allow_html=True). Tous les composants s'appuient sur
les classes CSS définies dans assets/elevenfield.css (préfixe `ef-`).

Convention : chaque helper retourne une chaîne HTML, ne fait JAMAIS d'appel
à st.* (afin de pouvoir composer plusieurs helpers dans un seul markdown).
"""
from __future__ import annotations

from typing import Iterable, Optional

import streamlit as st


# ── Couleurs heatmap percentile (5 paliers) ───────────────────────────────────

def pct_color_css(percentile: float) -> str:
    """Variable CSS de la couleur selon le percentile (0-100)."""
    if percentile is None:
        return "var(--ink-3)"
    if percentile < 20:  return "var(--pct-1)"
    if percentile < 40:  return "var(--pct-2)"
    if percentile < 60:  return "var(--pct-3)"
    if percentile < 80:  return "var(--pct-4)"
    return "var(--pct-5)"


def pos_class(pos: str) -> str:
    """Classe CSS de badge selon le groupe de position FBref."""
    if not pos:
        return ""
    pos_up = str(pos).upper()
    if "GK" in pos_up: return "pos-gk"
    if "DF" in pos_up: return "pos-def"
    if "MF" in pos_up: return "pos-mid"
    if "FW" in pos_up: return "pos-fwd"
    return ""


# ── Badges ────────────────────────────────────────────────────────────────────

def badge(text: str, variant: str = "") -> str:
    """
    variant : "" | "solid" | "pos-gk" | "pos-def" | "pos-mid" | "pos-fwd"
    """
    cls = "ef-badge" + (f" {variant}" if variant else "")
    return f'<span class="{cls}">{text}</span>'


# ── Section header ────────────────────────────────────────────────────────────

def section_header(title: str, hint: str = "") -> str:
    hint_html = f'<span class="sh">{hint}</span>' if hint else ""
    return (
        f'<div class="ef-section-h">'
        f'<span class="h">{title}</span>{hint_html}</div>'
    )


# ── Card wrapper ──────────────────────────────────────────────────────────────

def card_open(title: str = "", actions_html: str = "") -> str:
    """Ouvre une carte. À fermer avec card_close()."""
    hd = ""
    if title:
        hd = (
            f'<div class="ef-card-hd">'
            f'<span class="title">{title}</span>'
            f'<span class="spacer"></span>{actions_html}'
            f'</div>'
        )
    return f'<div class="ef-card">{hd}'


def card_close() -> str:
    return "</div>"


def card(title: str, body_html: str, actions_html: str = "") -> str:
    """Carte complète one-shot."""
    return card_open(title, actions_html) + body_html + card_close()


# ── Stat tile ─────────────────────────────────────────────────────────────────

def stat_tile(label: str, value: str, delta: Optional[str] = None,
              delta_dir: str = "") -> str:
    """
    delta_dir : "" | "up" | "down" (couleur verte/rouge)
    """
    delta_html = ""
    if delta:
        dc = f" {delta_dir}" if delta_dir else ""
        delta_html = f'<div class="delta{dc}">{delta}</div>'
    return (
        f'<div class="ef-stat">'
        f'<div class="k">{label}</div>'
        f'<div class="v">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )


def stat_grid(tiles: Iterable[str], cols: int = 4, gap: str = "8px") -> str:
    """Grille CSS de stat tiles."""
    inner = "".join(tiles)
    return (
        f'<div style="display:grid;grid-template-columns:repeat({cols},1fr);'
        f'gap:{gap}">{inner}</div>'
    )


# ── Percentile row ────────────────────────────────────────────────────────────

def pct_row(label: str, percentile: float, value: str = "",
            sub: str = "") -> str:
    """
    Une ligne percentile : libellé à gauche, barre au milieu, valeur à droite.
    `percentile` 0-100, `value` peut être "12 buts" ou "0.34".
    """
    p = max(0, min(100, percentile))
    color = pct_color_css(percentile)
    sub_html = f'<span class="sub">{sub}</span>' if sub else ""
    return (
        f'<div class="ef-pct-row">'
        f'  <div class="name">{label}{sub_html}</div>'
        f'  <div class="ef-pct-track">'
        f'    <div class="ef-pct-fill" style="width:{p:.0f}%;'
        f'background:{color};--pcol:{color}"></div>'
        f'  </div>'
        f'  <div class="num" style="color:{color}">{value or f"{int(round(p))}"}</div>'
        f'</div>'
    )


def pct_section(category: str, rows: list[tuple[str, float, str]]) -> str:
    """
    Section de percentiles groupés sous un nom de catégorie.
    rows : [(label, percentile, value_str), ...]
    """
    rows_html = "".join(pct_row(lbl, p, v) for lbl, p, v in rows)
    return (
        f'<div style="margin-bottom:14px">'
        f'  <div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;'
        f'color:var(--ink-3);margin-bottom:8px;font-weight:500">{category}</div>'
        f'  <div class="ef-pct">{rows_html}</div>'
        f'</div>'
    )


# ── Gauge (jauge SVG circulaire) ──────────────────────────────────────────────

def gauge_svg(value: float, max_value: float = 100,
              label: str = "", size: int = 120) -> str:
    """
    Jauge en arc (3/4 cercle). Couleur selon le score.
    """
    pct = max(0, min(1, value / max_value if max_value else 0))
    # Arc 270° (de -135 à +135), donc circumference utile = 270/360 * 2πr
    r = (size / 2) - 12
    cx = size / 2; cy = size / 2 + 4
    # Path d'arc 270°
    import math
    start_angle = -135 * math.pi / 180
    end_angle = 135 * math.pi / 180
    span = end_angle - start_angle
    cur_angle = start_angle + span * pct

    def _pt(angle: float) -> tuple[float, float]:
        return (cx + r * math.cos(angle), cy + r * math.sin(angle))

    sx, sy = _pt(start_angle)
    ex, ey = _pt(end_angle)
    px, py = _pt(cur_angle)

    large_track = 1  # 270° > 180°
    large_value = 1 if (cur_angle - start_angle) > math.pi else 0

    color = pct_color_css(value if max_value == 100 else 100 * value / max_value)

    return (
        f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px">'
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'  <path d="M {sx:.1f} {sy:.1f} A {r} {r} 0 {large_track} 1 {ex:.1f} {ey:.1f}"'
        f'        fill="none" stroke="var(--bg-3)" stroke-width="9" stroke-linecap="round"/>'
        f'  <path d="M {sx:.1f} {sy:.1f} A {r} {r} 0 {large_value} 1 {px:.1f} {py:.1f}"'
        f'        fill="none" stroke="{color}" stroke-width="9" stroke-linecap="round"/>'
        f'  <text x="{cx}" y="{cy + 4}" text-anchor="middle" fill="var(--ink-0)" '
        f'        font-size="{int(size * 0.28)}" font-weight="700">{int(round(value))}</text>'
        f'  <text x="{cx}" y="{cy + 22}" text-anchor="middle" fill="var(--ink-3)" '
        f'        font-size="9" letter-spacing="0.1em">/ {int(max_value)}</text>'
        f'</svg>'
        + (f'<div style="font-size:11px;color:var(--ink-2);text-align:center;'
           f'margin-top:-4px">{label}</div>' if label else "")
        + '</div>'
    )


# ── Empty state ───────────────────────────────────────────────────────────────

def empty_state(primary: str, secondary: str, icon: str = "◉") -> str:
    return (
        f'<div class="ef-empty">'
        f'  <div class="glyph">{icon}<span class="pulse"></span></div>'
        f'  <div class="primary">{primary}</div>'
        f'  <div class="hint">{secondary}</div>'
        f'</div>'
    )


# ── Topbar (breadcrumbs + filtres) ────────────────────────────────────────────

LEAGUE_CHIP_COLOR = {
    "ENG-Premier League": "var(--lg-pl)",
    "ESP-La Liga":        "var(--lg-laliga)",
    "GER-Bundesliga":     "var(--lg-bund)",
    "ITA-Serie A":        "var(--lg-seriea)",
    "FRA-Ligue 1":        "var(--lg-l1)",
}

LEAGUE_SHORT = {
    "ENG-Premier League": "PL",
    "ESP-La Liga":        "LIGA",
    "GER-Bundesliga":     "BUND",
    "ITA-Serie A":        "SA",
    "FRA-Ligue 1":        "L1",
}


def topbar_html(mode: str, tab_label: str, tab_hint: str,
                season_label: str, league: str) -> str:
    """
    Top header bar : mini-brand + breadcrumbs + saison + chips ligues.
    Style header app full-width inspiré du design Claude.
    """
    mode_lbl = "👤 Joueurs" if mode == "player" else "🏟 Clubs"
    hint = f'<span class="hint">· {tab_hint}</span>' if tab_hint else ""

    # Chips ligues (toutes en visible si "Toutes les ligues")
    if league == "Toutes les ligues":
        chips = "".join(
            f'<span class="ef-chip"><span class="swatch" style="background:{c}"></span>{LEAGUE_SHORT[k]}</span>'
            for k, c in LEAGUE_CHIP_COLOR.items()
        )
    else:
        c = LEAGUE_CHIP_COLOR.get(league, "var(--accent)")
        chips = (
            f'<span class="ef-chip" style="border-color:{c};color:var(--ink-0)">'
            f'<span class="swatch" style="background:{c}"></span>'
            f'{LEAGUE_SHORT.get(league, league)}'
            f'</span>'
        )

    return (
        f'<div class="ef-topbar">'
        f'  <div class="brand-mini">'
        f'    <div class="ef-brand-mark"></div>'
        f'    <div>'
        f'      <div class="brand-label">ELEVEN<span class="dot">·</span>FIELD</div>'
        f'      <div class="brand-sub">BIG 5 · {season_label}</div>'
        f'    </div>'
        f'  </div>'
        f'  <div class="ef-crumbs">'
        f'    <span>{mode_lbl}</span>'
        f'    <span class="sep">/</span>'
        f'    <span class="now">{tab_label}</span>'
        f'    {hint}'
        f'  </div>'
        f'  <div class="spacer"></div>'
        f'  <div class="season-block">'
        f'    <span class="lbl">Saison</span>'
        f'    <span class="val">{season_label}</span>'
        f'  </div>'
        f'  <span class="leagues-label">Ligues</span>'
        f'  <div style="display:flex;align-items:center;gap:4px">{chips}</div>'
        f'</div>'
    )


# ── Story board : pin / unpin ────────────────────────────────────────────────

def pitch_heatmap_svg(
    blobs: list[tuple[float, float, float, float]],
    width: int = 200,
    height: int = 280,
    direction: str = "up",
) -> str:
    """
    Mini-terrain vertical SVG avec rayures tondues + blobs de chaleur.
    IMPORTANT : tout le SVG est concaténé sans indentation pour éviter que
    Markdown ne l'interprète comme un bloc de code (>= 4 espaces en début
    de ligne → bloc <code>).
    """
    stripe_count = 8
    stripes_svg = "".join(
        f'<rect x="0" y="{i * (height / stripe_count)}" width="{width}" '
        f'height="{height / stripe_count}" '
        f'fill="{"#1e4a2e" if i % 2 == 0 else "#234d33"}" />'
        for i in range(stripe_count)
    )

    lc = "rgba(255,255,255,0.35)"
    lines_svg = (
        f'<rect x="4" y="4" width="{width-8}" height="{height-8}" '
        f'fill="none" stroke="{lc}" stroke-width="1.5"/>'
        f'<line x1="4" x2="{width-4}" y1="{height/2}" y2="{height/2}" '
        f'stroke="{lc}" stroke-width="1.2"/>'
        f'<circle cx="{width/2}" cy="{height/2}" r="22" fill="none" '
        f'stroke="{lc}" stroke-width="1.2"/>'
        f'<circle cx="{width/2}" cy="{height/2}" r="2" fill="{lc}"/>'
        f'<rect x="{(width-70)/2}" y="4" width="70" height="36" '
        f'fill="none" stroke="{lc}" stroke-width="1.2"/>'
        f'<rect x="{(width-32)/2}" y="4" width="32" height="14" '
        f'fill="none" stroke="{lc}" stroke-width="1.2"/>'
        f'<rect x="{(width-70)/2}" y="{height-40}" width="70" height="36" '
        f'fill="none" stroke="{lc}" stroke-width="1.2"/>'
        f'<rect x="{(width-32)/2}" y="{height-18}" width="32" height="14" '
        f'fill="none" stroke="{lc}" stroke-width="1.2"/>'
    )

    blobs_svg = ""
    for x, y, r, intensity in blobs:
        cx = (x / 100) * width
        cy = (y / 100) * height
        radius = (r / 100) * min(width, height)
        op = min(0.85, max(0.15, intensity))
        blobs_svg += (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" '
            f'fill="url(#heat-grad)" opacity="{op}"/>'
        )

    arrow_y = 20 if direction == "down" else (height - 20)
    arrow_dir = "▼" if direction == "down" else "▲"
    arrow_svg = (
        f'<text x="{width-14}" y="{arrow_y}" font-size="14" '
        f'fill="rgba(255,255,255,0.6)" text-anchor="middle">{arrow_dir}</text>'
    )

    # Concaténation sans newline/indent — empêche Markdown de transformer en code-block
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="border-radius:8px;background:#1e4a2e;display:block">'
        f'<defs>'
        f'<radialGradient id="heat-grad">'
        f'<stop offset="0%" stop-color="#84e06e" stop-opacity="0.85"/>'
        f'<stop offset="40%" stop-color="#84e06e" stop-opacity="0.45"/>'
        f'<stop offset="100%" stop-color="#84e06e" stop-opacity="0"/>'
        f'</radialGradient>'
        f'</defs>'
        f'{stripes_svg}{lines_svg}{blobs_svg}{arrow_svg}'
        f'</svg>'
    )


def pin_button(card_id: str, title: str, subtitle: str = "",
               card_type: str = "generic") -> None:
    """
    Bouton ✦ Story sur une card épinglable.
    Toggle l'item dans st.session_state["ef_board"] (liste de dicts).
    Appel : pin_button("mbappe-gauge", "Indice de performance", "Mbappé 91/100", "gauge")
    """
    board = st.session_state.setdefault("ef_board", [])
    is_pinned = any(item["id"] == card_id for item in board)
    label = "✓ Dans la Story" if is_pinned else "✦ Story"
    btn_type = "primary" if is_pinned else "secondary"

    if st.button(label, key=f"pin_{card_id}", type=btn_type):
        if is_pinned:
            st.session_state["ef_board"] = [
                i for i in board if i["id"] != card_id
            ]
        else:
            st.session_state["ef_board"].append({
                "id": card_id, "title": title, "subtitle": subtitle,
                "type": card_type,
            })
        st.rerun()


# ── Helper : inject CSS at app start ──────────────────────────────────────────

def inject_design_css() -> None:
    """Charge assets/elevenfield.css et l'injecte dans la page."""
    from pathlib import Path
    css_path = Path(__file__).parent.parent / "assets" / "elevenfield.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
