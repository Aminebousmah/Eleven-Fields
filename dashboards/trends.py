"""
Dashboard Tendances.
Auto-surface les patterns intéressants : sur/sous-performeurs xG,
jeunes à fort impact, styles atypiques, comparaison inter-saisons.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from config import COLORS, LEAGUE_LABELS, CLUSTER_NAMES, SEASONS
from components.flags import get_flag_url
from components.kpi_cards import render_section_header, render_kpi_row
from components.charts import make_peer_scatter, make_bar_comparison
from data.loader import load_team_season_stats, load_player_season_stats
from data.processor import (
    find_xg_outliers, find_defensive_outliers, find_young_stars,
    find_style_outliers, find_player_xg_outliers,
)
from components.design import card_open, card_close, pct_color_css

try:
    from transfermarkt.matcher import enrich_with_logos, enrich_with_photos, format_value
    TM_AVAILABLE = True
except Exception:
    TM_AVAILABLE = False
    def enrich_with_logos(df, *a, **kw): return df
    def enrich_with_photos(df, *a, **kw): return df
    def format_value(v): return "—"


def _logo_cfg(): return st.column_config.ImageColumn("Logo", width="small")
def _photo_cfg(): return st.column_config.ImageColumn("Photo", width="small")


def _show_team_table(df, league, cols_after_logo, **fmt) -> None:
    """Helper : injecte logo_url + affiche en dataframe avec ImageColumn."""
    if df is None or df.empty:
        return
    df = enrich_with_logos(df, team_col="team", league=league)
    show = ["logo_url", "team"] + [c for c in cols_after_logo if c in df.columns]
    show = [c for c in show if c in df.columns]
    rename = {"logo_url": "Logo", "team": "Équipe"}
    column_config = {"Logo": _logo_cfg()} if "logo_url" in df.columns else {}
    st.dataframe(
        df[show].rename(columns=rename),
        hide_index=True, use_container_width=True, column_config=column_config,
    )


def render(season: str, league: str) -> None:
    league_f = None if league == "Toutes les ligues" else league

    # ── Filter rail horizontal (mockup 5) ────────────────────────────────────
    st.markdown(
        '<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;'
        'margin-bottom:14px;border-radius:10px;background:var(--bg-1);'
        'border:1px solid var(--line-faint)">'
        '<span style="font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;'
        'color:var(--ink-3);margin-right:4px">Tendances · sur/sous-performeurs xG</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Gate empty state
    from components.filters import render_show_gate
    if not render_show_gate(
        "trends_stats",
        label="📊  Afficher les tendances",
        primary_text="Configure tes filtres",
        hint="Ajuste saison et ligue dans le bouton ⚙ ci-dessus, puis clique pour générer.",
        icon="△",
    ):
        return

    # ── 2 colonnes : ↑ Sur-performeurs / ↓ Sous-performeurs ─────────────────
    outliers = find_player_xg_outliers(season, league_f, top_n=5, min_minutes=600)

    c_over, c_under = st.columns(2, gap="medium")

    with c_over:
        n_over = len(outliers["over"])
        st.markdown(
            card_open(
                "↑  Sur-performeurs xG",
                actions_html=f'<span style="color:var(--ink-3);font-size:11px">{n_over} joueurs</span>',
            ),
            unsafe_allow_html=True,
        )
        if outliers["over"].empty:
            st.markdown(
                '<div style="font-size:12px;color:var(--ink-3);padding:18px 0;'
                'text-align:center">Pas de données.</div>',
                unsafe_allow_html=True,
            )
        else:
            for _, row in outliers["over"].iterrows():
                _render_xg_outlier_row(row, sign="+")
        st.markdown(card_close(), unsafe_allow_html=True)

    with c_under:
        n_under = len(outliers["under"])
        st.markdown(
            card_open(
                "↓  Sous-performeurs xG",
                actions_html=f'<span style="color:var(--ink-3);font-size:11px">{n_under} joueurs</span>',
            ),
            unsafe_allow_html=True,
        )
        if outliers["under"].empty:
            st.markdown(
                '<div style="font-size:12px;color:var(--ink-3);padding:18px 0;'
                'text-align:center">Pas de données.</div>',
                unsafe_allow_html=True,
            )
        else:
            for _, row in outliers["under"].iterrows():
                _render_xg_outlier_row(row, sign="-")
        st.markdown(card_close(), unsafe_allow_html=True)

    # ── Section Intelligence Médias (Claude Haiku) ──────────────────────────
    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
    _render_media_feed(outliers, season, league_f)


# Flux médias mock (mockup 5) — à brancher sur vrai RSS + Claude Haiku plus tard
_NEWS_MOCK = [
    {"source": "Marca", "club": "Real Madrid",
     "title": "Mbappé décisif au Bernabéu, son meilleur match cette saison",
     "sentiment": "pos", "tag": "Performance", "delay": "il y a 12 min"},
    {"source": "L'Équipe", "club": "PSG",
     "title": "Dembélé prolongé jusqu'en 2028, signal fort de la direction",
     "sentiment": "pos", "tag": "Tactique", "delay": "il y a 38 min"},
    {"source": "Sky Sports", "club": "Arsenal",
     "title": "Saka victime d'une lésion mineure, indisponible 2 à 3 semaines",
     "sentiment": "neg", "tag": "Blessure", "delay": "il y a 1h"},
    {"source": "Gazzetta", "club": "Inter",
     "title": "Lautaro : « Le Scudetto se joue dans les détails maintenant »",
     "sentiment": "neu", "tag": "Mercato", "delay": "il y a 2h"},
    {"source": "Bild", "club": "Bayern",
     "title": "Musiala revient à l'entraînement collectif",
     "sentiment": "pos", "tag": "Récompense", "delay": "il y a 3h"},
    {"source": "Mundo Dep.", "club": "FC Barcelona",
     "title": "Yamal nommé pour le Golden Boy 2026",
     "sentiment": "pos", "tag": "Polémique", "delay": "il y a 4h"},
]


def _render_media_feed(outliers: dict, season: str, league_f: str | None) -> None:
    """Intelligence Médias : 6 cards générées par Claude Haiku à partir des outliers réels."""
    # Statut clé API
    import os
    has_key = bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or (st.secrets.get("ANTHROPIC_API_KEY", None) if hasattr(st, "secrets") else None)
    )
    badge_html = (
        '<span class="ef-badge solid" style="background:var(--good);color:var(--accent-ink)">Claude Haiku</span>'
        if has_key else
        '<span class="ef-badge" style="color:var(--warn)">Mode fallback</span>'
    )

    st.markdown(
        card_open("Intelligence Médias · analysé par Haiku",
                  actions_html=badge_html
                               + ' &nbsp;<span style="color:var(--ink-3);font-size:11px">↻ cache 1h</span>'),
        unsafe_allow_html=True,
    )

    items = _generate_media_intel(outliers, season, league_f, has_key)

    # Grille 2 colonnes
    cols = st.columns(2, gap="medium")
    for i, news in enumerate(items):
        with cols[i % 2]:
            _render_news_card(news)

    st.markdown(card_close(), unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def _generate_media_intel(_outliers: dict, season: str, league_f: str | None, has_key: bool) -> list[dict]:
    """Appel Claude Haiku pour générer 6 mini-news à partir des outliers xG réels.
    Fallback sur _NEWS_MOCK si pas de clé ou erreur."""
    if not has_key:
        return _NEWS_MOCK

    over = _outliers.get("over", pd.DataFrame())
    under = _outliers.get("under", pd.DataFrame())
    if (over is None or over.empty) and (under is None or under.empty):
        return _NEWS_MOCK

    def _rows(df, kind):
        out = []
        if df is None or df.empty:
            return out
        for _, r in df.head(4).iterrows():
            try:
                out.append({
                    "kind": kind,
                    "player": str(r.get("player", "")),
                    "team": str(r.get("team", "")),
                    "league": str(r.get("league", "")),
                    "Gls": int(round(float(r.get("Gls", 0)))),
                    "xG": round(float(r.get("xG", 0)), 1),
                    "diff": round(float(r.get("Gls-xG", 0)), 1),
                })
            except Exception:
                continue
        return out

    data = {
        "season": season,
        "league": league_f or "Big 5",
        "over_performers": _rows(over, "over"),
        "under_performers": _rows(under, "under"),
    }

    prompt = (
        "Tu es un analyste data football. À partir des données réelles d'écart "
        "buts/xG ci-dessous, génère exactement 6 mini-news courtes en français "
        "(style brève sportive, 1 phrase chacune). Mélange sur-performeurs et "
        "sous-performeurs. Chaque news doit citer le joueur, son club, et un "
        "chiffre clé (buts, xG ou écart). Pas d'émojis. Pas de hashtags.\n\n"
        f"DONNÉES :\n{data}\n\n"
        "Réponds UNIQUEMENT par un tableau JSON valide, format strict :\n"
        '[{"source":"<nom média plausible: L\'Équipe, Marca, Sky Sports, Gazzetta, Bild, Mundo Dep., The Athletic>",'
        '"club":"<club exact>",'
        '"title":"<1 phrase, max 110 caractères, chiffre en évidence>",'
        '"sentiment":"<pos|neg|neu>",'
        '"tag":"<Performance|Finition|Efficacité|Forme|Inefficacité|Statistique>",'
        '"delay":"<il y a Xmin/Xh>"}]\n'
        "Aucun texte avant ou après le JSON."
    )

    try:
        import anthropic
        import os
        import json
        import re
        api_key = (
            os.environ.get("ANTHROPIC_API_KEY")
            or (st.secrets.get("ANTHROPIC_API_KEY", None) if hasattr(st, "secrets") else None)
        )
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # Extraire le JSON (au cas où Claude ajoute du texte autour)
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            return _NEWS_MOCK
        items = json.loads(m.group(0))
        # Garde 6 items max et valide les champs
        valid = []
        for it in items[:6]:
            if all(k in it for k in ("source", "club", "title", "sentiment", "tag", "delay")):
                if it["sentiment"] not in ("pos", "neg", "neu"):
                    it["sentiment"] = "neu"
                valid.append(it)
        return valid if valid else _NEWS_MOCK
    except Exception:
        return _NEWS_MOCK


def _render_news_card(news: dict) -> None:
    """Une carte news : source, club, titre, sentiment, badge."""
    sent_map = {
        "pos": ("↑ Positif", "var(--good)"),
        "neg": ("↓ Négatif", "var(--bad)"),
        "neu": ("· Neutre",  "var(--ink-3)"),
    }
    sent_label, sent_color = sent_map.get(news["sentiment"], ("·", "var(--ink-3)"))

    st.markdown(
        f'<div style="padding:12px 14px;margin-bottom:10px;border-radius:8px;'
        f'background:var(--bg-2);border:1px solid var(--line-faint);'
        f'border-left:3px solid {sent_color}">'
        f'  <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;'
        f'font-size:10px">'
        f'    <span style="font-family:ui-monospace,monospace;color:var(--ink-3);'
        f'letter-spacing:.04em">{news["source"]}</span>'
        f'    <span class="ef-badge" style="font-size:9px;height:16px;padding:0 5px">'
        f'{news["club"]}</span>'
        f'    <span style="margin-left:auto;color:var(--ink-3);font-size:10px">'
        f'{news["delay"]}</span>'
        f'  </div>'
        f'  <div style="font-size:13px;color:var(--ink-0);line-height:1.45;'
        f'font-weight:500;margin-bottom:6px">{news["title"]}</div>'
        f'  <div style="display:flex;gap:6px;align-items:center">'
        f'    <span style="font-size:10px;color:{sent_color};font-weight:600;'
        f'letter-spacing:.04em">{sent_label}</span>'
        f'    <span class="ef-badge" style="font-size:9px">{news["tag"]}</span>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_xg_outlier_row(row, sign: str = "+") -> None:
    """Une ligne joueur dans la liste sur/sous-performeurs."""
    player = row.get("player", "—")
    team = row.get("team", "")
    league = row.get("league", "")
    gls = row.get("Gls", 0)
    xg = row.get("xG", 0)
    diff = row.get("Gls-xG", 0)

    try:
        gls_str = f"{int(round(float(gls)))}"
    except Exception:
        gls_str = "—"
    try:
        xg_str = f"{float(xg):.1f}"
    except Exception:
        xg_str = "—"

    diff_color = "var(--good)" if sign == "+" else "var(--bad)"
    diff_sign = "+" if sign == "+" else ""
    try:
        diff_str = f"{diff_sign}{float(diff):.1f}"
    except Exception:
        diff_str = "—"

    # Initiales pour le placeholder (3 lettres)
    initials = "".join(w[0].upper() for w in player.split()[:2]) or "·"

    st.markdown(
        f'<div style="display:grid;grid-template-columns:32px 1fr 50px 50px 60px;'
        f'gap:14px;align-items:center;padding:10px 8px;'
        f'border-bottom:1px solid var(--line-faint)">'
        f'  <div style="width:32px;height:32px;border-radius:6px;'
        f'background:linear-gradient(135deg, color-mix(in oklch, {diff_color} 30%, var(--bg-2)), var(--bg-2));'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-family:ui-monospace,monospace;font-size:10.5px;'
        f'font-weight:700;color:var(--ink-0)">{initials}</div>'
        f'  <div style="min-width:0">'
        f'    <div style="font-size:13px;font-weight:600;color:var(--ink-0);'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{player}</div>'
        f'    <div style="font-size:10.5px;color:var(--ink-3);margin-top:2px">'
        f'{team} · {LEAGUE_LABELS.get(league, league)}</div>'
        f'  </div>'
        f'  <div style="text-align:right">'
        f'    <div style="font-family:ui-monospace,monospace;font-size:14px;'
        f'font-weight:600;color:var(--ink-0)">{gls_str}</div>'
        f'    <div style="font-size:8.5px;letter-spacing:.1em;color:var(--ink-3);'
        f'text-transform:uppercase">buts</div>'
        f'  </div>'
        f'  <div style="text-align:right">'
        f'    <div style="font-family:ui-monospace,monospace;font-size:14px;'
        f'font-weight:600;color:var(--ink-1)">{xg_str}</div>'
        f'    <div style="font-size:8.5px;letter-spacing:.1em;color:var(--ink-3);'
        f'text-transform:uppercase">xG</div>'
        f'  </div>'
        f'  <div style="text-align:right">'
        f'    <div style="font-family:ui-monospace,monospace;font-size:15px;'
        f'font-weight:700;color:{diff_color}">{diff_str}</div>'
        f'    <div style="font-size:8.5px;letter-spacing:.1em;color:var(--ink-3);'
        f'text-transform:uppercase">Δ</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Helpers internes ──────────────────────────────────────────────────────────

def _small_bar(df: pd.DataFrame, x: str, y: str, color: str) -> None:
    """Mini bar chart horizontal."""
    import plotly.graph_objects as go
    from config import PLOTLY_LAYOUT
    fig = go.Figure(go.Bar(
        x=df[y], y=df[x],
        orientation="h",
        marker_color=color,
        text=[f"{v:+.2f}" for v in df[y]],
        textposition="outside",
    ))
    layout = {**PLOTLY_LAYOUT}
    layout["margin"] = dict(l=10, r=40, t=10, b=20)
    fig.update_layout(
        **layout,
        yaxis=dict(autorange="reversed"),
        height=220,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _xg_vs_goals_scatter(season: str, league: str | None) -> None:
    """Scatter xG vs Buts."""
    import plotly.graph_objects as go
    from config import PLOTLY_LAYOUT

    std = load_team_season_stats("standard", [season])
    sht = load_team_season_stats("shooting", [season])
    if league and league != "Toutes les ligues":
        std = std[std["league"] == league]
        sht = sht[sht["league"] == league]

    m = std[["team", "Gls"]].merge(sht[["team", "xG"]], on="team", how="inner")
    m["Gls"] = pd.to_numeric(m["Gls"], errors="coerce")
    m["xG"] = pd.to_numeric(m["xG"], errors="coerce")
    m = m.dropna()

    if m.empty:
        st.info("Données indisponibles.")
        return

    m["diff"] = m["Gls"] - m["xG"]
    colors = [COLORS["accent_green"] if d > 0 else COLORS["accent_red"] for d in m["diff"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=m["xG"], y=m["Gls"],
        mode="markers+text",
        text=m["team"],
        textposition="top center",
        textfont=dict(color=COLORS["text"], size=10),
        marker=dict(color=colors, size=10, line=dict(color=COLORS["border"], width=1)),
        hovertemplate="<b>%{text}</b><br>xG: %{x:.1f}<br>Buts: %{y}<extra></extra>",
    ))
    # Diagonale
    lim = max(m["xG"].max(), m["Gls"].max()) + 2
    fig.add_shape(type="line", x0=0, y0=0, x1=lim, y1=lim,
                  line=dict(color=COLORS["text_muted"], width=1, dash="dash"))

    fig.update_layout(
        **PLOTLY_LAYOUT,
        xaxis=dict(title="xG", gridcolor=COLORS["grid"]),
        yaxis=dict(title="Buts", gridcolor=COLORS["grid"]),
        height=500,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _season_evolution(s_prev: str, s_curr: str, league: str | None) -> None:
    """Comparaison xG, Pts (proxy), possession entre deux saisons."""
    metrics = [
        ("shooting", "xG", "xG"),
        ("standard", "Poss", "Possession"),
        ("goal_shot_creation", "SCA", "SCA"),
        ("defense", "Tkl", "Tacles"),
    ]

    # Récupère Gls depuis standard
    std_prev = load_team_season_stats("standard", [s_prev])
    std_curr = load_team_season_stats("standard", [s_curr])
    if league and league != "Toutes les ligues":
        std_prev = std_prev[std_prev["league"] == league]
        std_curr = std_curr[std_curr["league"] == league]

    # Teams communes
    common = sorted(set(std_prev["team"]).intersection(set(std_curr["team"])))
    if not common:
        st.info("Aucune équipe commune aux deux saisons (changements de ligue ?).")
        return

    metric_choice = st.selectbox(
        "Métrique à comparer",
        [m[2] for m in metrics],
        key="trends_metric",
    )
    st_type, col, label = next(m for m in metrics if m[2] == metric_choice)

    df_prev = load_team_season_stats(st_type, [s_prev])
    df_curr = load_team_season_stats(st_type, [s_curr])
    if league and league != "Toutes les ligues":
        df_prev = df_prev[df_prev["league"] == league]
        df_curr = df_curr[df_curr["league"] == league]

    if col not in df_prev.columns or col not in df_curr.columns:
        st.warning(f"Colonne {col} manquante.")
        return

    dp = df_prev[df_prev["team"].isin(common)][["team", col]].rename(columns={col: s_prev})
    dc = df_curr[df_curr["team"].isin(common)][["team", col]].rename(columns={col: s_curr})
    m = dp.merge(dc, on="team", how="inner")
    for c in [s_prev, s_curr]:
        m[c] = pd.to_numeric(m[c], errors="coerce")
    m["Δ"] = m[s_curr] - m[s_prev]
    m = m.dropna().sort_values("Δ", ascending=False)

    # Top/Bottom progresseurs
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"<div style='color:{COLORS['accent_green']};font-weight:700'>📈 Plus grosses progressions</div>",
                    unsafe_allow_html=True)
        top = m.head(5)
        _small_bar(top, "team", "Δ", COLORS["accent_green"])
    with c2:
        st.markdown(f"<div style='color:{COLORS['accent_red']};font-weight:700'>📉 Plus grosses régressions</div>",
                    unsafe_allow_html=True)
        bot = m.tail(5).sort_values("Δ")
        _small_bar(bot, "team", "Δ", COLORS["accent_red"])

    st.divider()
    render_section_header(f"Tableau complet — {label}")
    disp = m.rename(columns={"team": "Équipe"})
    styled = disp.style.format(precision=2, na_rep="—").background_gradient(
        subset=["Δ"], cmap="RdYlGn", vmin=-m["Δ"].abs().max(), vmax=m["Δ"].abs().max()
    )
    st.dataframe(styled, hide_index=True, use_container_width=True)
