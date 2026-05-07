"""
Carte de rapport visuel style Data'Scout.
6 sections fixes (FINITION / CRÉATION / CONSTRUCTION / OFFENSIF / DÉFENSE / AÉRIEN)
avec labels en français et percentiles par rapport aux joueurs de même position.

render_player_report_card(player, team, pos_group, season, league_filter)
render_club_report_card(team, season, league_filter)
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import COLORS, SEASONS, LEAGUE_LABELS


# ── Sections joueur : {label FR : (stat_type, col_fbref)} ────────────────────
# Identiques pour tous les postes — seuls les percentiles changeront.
# build_percentiles_labeled accepte un dict {label: (stat_type, col)}.

REPORT_SECTIONS_PLAYER: list[tuple[str, dict[str, tuple[str, str]]]] = [
    ("FINITION", {
        "Buts":                    ("standard",  "Gls"),
        "xG":                      ("shooting",  "xG"),
        "Buts hors penalty (xG)":  ("shooting",  "npxG"),
        "Surperf. / xG":           ("shooting",  "G-xG"),
        "Conversion but/tir":      ("shooting",  "G/Sh"),
        "Tirs cadrés %":           ("shooting",  "SoT%"),
    }),
    ("CRÉATION", {
        "Passes décisives":        ("passing",            "Ast"),
        "xA":                      ("passing",            "xAG"),
        "Actions créatrices":      ("goal_shot_creation", "SCA"),
        "Passes clés":             ("passing",            "KP"),
        "Passes dernier tiers":    ("passing",            "1/3"),
        "Passes vers la surface":  ("passing",            "PPA"),
        "Centres réussis":         ("passing",            "CrsPA"),
    }),
    ("CONSTRUCTION", {
        "Passes réceptionnées":    ("possession", "PrgR"),
        "Passes réussies %":       ("passing",    "Cmp%"),
        "Passes longues %":        ("passing",    "Cmp%_3"),
        "Passes progressives":     ("passing",    "PrgP"),
        "Distance de passe progr.":("passing",    "PrgDist"),
    }),
    ("OFFENSIF", {
        "Dribbles réussis":        ("possession", "Succ"),
        "Dribbles réussis %":      ("possession", "Succ%"),
        "Courses progressives":    ("standard",   "PrgC"),
        "Fautes subies":           ("misc",       "Fld"),
    }),
    ("DÉFENSE", {
        "Interceptions":           ("defense",    "Int"),
        "Tacles gagnés":           ("defense",    "TklW"),
        "Tacles":                  ("defense",    "Tkl"),
        "Blocs":                   ("defense",    "Blocks"),
        "Dégagements":             ("defense",    "Clr"),
    }),
    ("AÉRIEN", {
        "Duels aériens gagnés":    ("misc", "Won"),
        "Duels aériens %":         ("misc", "Won%"),
    }),
]

# Phrases points forts / axes d'amélioration
_STRENGTH_PHRASES: dict[str, str] = {
    "Buts":                    "Marque beaucoup",
    "xG":                      "Fort potentiel offensif",
    "Buts hors penalty (xG)":  "Dangereux hors penaltys",
    "Surperf. / xG":           "Surperforme son xG",
    "Conversion but/tir":      "Très bonne finition",
    "Tirs cadrés %":           "Précis dans ses tirs",
    "Passes décisives":        "Passeur décisif",
    "xA":                      "Forte capacité à créer",
    "Actions créatrices":      "Multiplie les actions créatrices",
    "Passes clés":             "Maître des passes clés",
    "Passes dernier tiers":    "Pénètre le dernier tiers",
    "Passes vers la surface":  "Alimente la surface",
    "Centres réussis":         "Centreur précis",
    "Passes réceptionnées":    "Reçoit beaucoup de ballons prog.",
    "Passes réussies %":       "Passe proprement",
    "Passes longues %":        "Précis sur les longues passes",
    "Passes progressives":     "Fait progresser le jeu",
    "Distance de passe progr.":"Progression constante par la passe",
    "Dribbles réussis":        "Élimination efficace",
    "Dribbles réussis %":      "Taux de réussite élevé en dribble",
    "Courses progressives":    "Progressif balle au pied",
    "Fautes subies":           "Provoque des fautes",
    "Interceptions":           "Intercepte beaucoup",
    "Tacles gagnés":           "Gagne ses duels défensifs",
    "Tacles":                  "Actif défensivement",
    "Blocs":                   "Bloque beaucoup",
    "Dégagements":             "Dégage bien",
    "Duels aériens gagnés":    "Dominant dans les airs",
    "Duels aériens %":         "Fort en pourcentage aérien",
}

_WEAKNESS_PHRASES: dict[str, str] = {
    "Buts":                    "Peu de buts marqués",
    "xG":                      "Peu dangereux devant le but",
    "Buts hors penalty (xG)":  "Peu d'impact hors penaltys",
    "Surperf. / xG":           "Ne performe pas son xG",
    "Conversion but/tir":      "Finition à améliorer",
    "Tirs cadrés %":           "Manque de précision dans les tirs",
    "Passes décisives":        "Peu de passes décisives",
    "xA":                      "Peu de créativité offensiv",
    "Actions créatrices":      "Peu d'actions créatrices",
    "Passes clés":             "Peu de passes clés",
    "Passes dernier tiers":    "Peu de passes vers le dernier tiers",
    "Passes vers la surface":  "Peu d'alimentation de la surface",
    "Centres réussis":         "Centreur peu précis",
    "Passes réceptionnées":    "Peu de ballons progressifs reçus",
    "Passes réussies %":       "Déchet technique important",
    "Passes longues %":        "Manque de précision long",
    "Passes progressives":     "Ne fait pas progresser le ballon",
    "Distance de passe progr.":"Progression faible par la passe",
    "Dribbles réussis":        "Peu de dribbles réussis",
    "Dribbles réussis %":      "Dribbles peu efficaces",
    "Courses progressives":    "Peu progressif balle au pied",
    "Fautes subies":           "Peu de fautes provoquées",
    "Interceptions":           "Peu d'interceptions",
    "Tacles gagnés":           "Dispute peu de duels défensifs",
    "Tacles":                  "Peu actif défensivement",
    "Blocs":                   "Peu de blocs",
    "Dégagements":             "Peu de dégagements",
    "Duels aériens gagnés":    "Peu à l'aise dans les airs",
    "Duels aériens %":         "Dispute peu de duels aériens",
}


# ── Helpers HTML ──────────────────────────────────────────────────────────────

def _pct_bar(label: str, pct: float, bold: bool = False) -> str:
    fill = max(0.0, min(100.0, float(pct)))
    bar_color = (
        COLORS["accent_green"] if fill >= 70 else
        COLORS["accent_gold"]  if fill >= 40 else
        COLORS["accent_red"]
    )
    lbl_style = "font-weight:700;" if bold else ""
    return (
        '<div style="margin-bottom:8px">'
        '<div style="display:flex;justify-content:space-between;align-items:center;'
        'font-size:0.72rem;margin-bottom:2px">'
        '<span style="color:' + COLORS["text"] + ';' + lbl_style + '">' + label + '</span>'
        '<span style="color:' + bar_color + ';font-weight:700;min-width:24px;text-align:right">'
        + f"{fill:.0f}" + '</span>'
        '</div>'
        '<div style="height:5px;background:' + COLORS["border"] + ';border-radius:3px;overflow:hidden">'
        '<div style="width:' + f"{fill:.1f}" + '%;height:100%;background:' + bar_color + ';'
        'border-radius:3px"></div>'
        '</div>'
        '</div>'
    )


def _section_box(title: str, bars_html: str) -> str:
    return (
        '<div style="margin-bottom:14px">'
        '<div style="font-size:0.65rem;font-weight:700;color:' + COLORS["text_muted"] + ';'
        'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:7px">' + title + '</div>'
        '<div style="background:' + COLORS["surface"] + ';border:1px solid ' + COLORS["border"] + ';'
        'border-radius:8px;padding:11px 13px">'
        + bars_html +
        '</div>'
        '</div>'
    )


def _card_box(content: str, mb: str = "12px") -> str:
    return (
        '<div style="background:' + COLORS["card"] + ';border:1px solid ' + COLORS["border"] + ';'
        'border-radius:12px;padding:14px 16px;margin-bottom:' + mb + '">'
        + content +
        '</div>'
    )


def _kpi_chip(label: str, value: str, color: str) -> str:
    return (
        '<div style="background:' + COLORS["surface"] + ';border:1px solid ' + COLORS["border"] + ';'
        'border-radius:8px;padding:7px 11px;text-align:center">'
        '<div style="font-size:1.0rem;font-weight:800;color:' + color + '">' + value + '</div>'
        '<div style="font-size:0.63rem;color:' + COLORS["text_muted"] + ';margin-top:1px;white-space:nowrap">'
        + label + '</div>'
        '</div>'
    )


def _sw_chip(text: str, good: bool) -> str:
    color = COLORS["accent_green"] if good else COLORS["accent_red"]
    return (
        '<div style="background:' + COLORS["surface"] + ';border-left:3px solid ' + color + ';'
        'border-radius:0 6px 6px 0;padding:6px 10px;margin-bottom:5px;'
        'font-size:0.76rem;color:' + COLORS["text"] + '">'
        + text +
        '</div>'
    )


def _similar_row(name: str, subtitle: str, compat: float) -> str:
    return (
        '<div style="display:flex;justify-content:space-between;align-items:center;'
        'padding:6px 0;border-bottom:1px solid ' + COLORS["border"] + '">'
        '<div>'
        '<div style="font-size:0.82rem;color:' + COLORS["text"] + ';font-weight:600">' + name + '</div>'
        '<div style="font-size:0.7rem;color:' + COLORS["text_muted"] + '">' + subtitle + '</div>'
        '</div>'
        '<span style="font-size:0.82rem;color:' + COLORS["accent_green"] + ';font-weight:800">'
        + f"{compat:.0f}%" +
        '</span>'
        '</div>'
    )


# ── Carte joueur ──────────────────────────────────────────────────────────────

def render_player_report_card(
    player: str,
    team: str,
    pos_group: str,
    season: str,
    league_filter: str | None,
) -> None:
    from data.loader import load_player_season_stats
    from data.processor import (
        build_percentiles_labeled,
        compute_dominant_profile,
        find_similar_players,
    )
    try:
        from transfermarkt.matcher import (
            match_player, format_value, get_club_logo, get_player_value_season,
        )
    except Exception:
        def match_player(*a, **kw): return None
        def format_value(v): return "—"
        def get_club_logo(*a, **kw): return None
        def get_player_value_season(*a, **kw): return None

    # ── Données ───────────────────────────────────────────────────────────────
    std = load_player_season_stats("standard", [season])
    if league_filter:
        std = std[std["league"] == league_filter]
    row = std[(std["player"] == player) & (std["team"] == team)]
    if row.empty:
        st.warning("Données insuffisantes pour générer la carte.")
        return
    r = row.iloc[0]

    def fmt(v, d=1):
        try:
            return f"{float(v):.{d}f}"
        except Exception:
            return "—"

    season_label = SEASONS.get(season, season)
    league_label = LEAGUE_LABELS.get(league_filter, league_filter or "Big 5")

    tm           = match_player(player, fbref_league=league_filter) or {}
    photo_url    = tm.get("image_url", "")
    # Valeur historique à la fin de la saison sélectionnée
    market_value = get_player_value_season(player, season, league_filter)
    nationality  = (r.get("nation") or "").split()[-1] if pd.notna(r.get("nation", None)) else ""
    foot         = tm.get("foot", "")
    age          = r.get("age", "—")
    pos          = r.get("pos", pos_group)
    logo_url     = get_club_logo(team, league_filter) or ""
    val_str      = format_value(market_value) if market_value and pd.notna(market_value) else "—"

    # Profil dominant
    dominant, dom_score, all_scores = compute_dominant_profile(
        player, team, season, league_filter, min_minutes=500, pos_group=pos_group,
    )

    # Similaires (top 3)
    try:
        sim = find_similar_players(player, team, season, league_filter,
                                   pos_group=pos_group, n=3, min_minutes=300)
        sim_list = sim[["player", "team", "compat_pct"]].values.tolist() if not sim.empty else []
    except Exception:
        sim_list = []

    # ── Percentiles par section ───────────────────────────────────────────────
    all_pct: dict[str, dict] = {}   # label → row
    rendered_sections: list[tuple[str, list[dict]]] = []

    for sec_title, metrics_dict in REPORT_SECTIONS_PLAYER:
        items = build_percentiles_labeled(
            metrics_dict, player, "player", season, league_filter, min_minutes=300,
        )
        if items:
            for item in items:
                all_pct[item["metric"]] = item
            rendered_sections.append((sec_title, items))

    # Points forts / Axes d'amélioration
    by_pct = sorted(all_pct.values(), key=lambda x: x["percentile"], reverse=True)
    strengths  = [p for p in by_pct if p["percentile"] >= 75][:3]
    weaknesses = sorted([p for p in by_pct if p["percentile"] <= 30], key=lambda x: x["percentile"])[:3]

    # ── HTML identité ─────────────────────────────────────────────────────────
    if photo_url:
        photo_html = (
            '<img src="' + photo_url + '" style="width:88px;height:88px;object-fit:cover;'
            'border-radius:50%;border:3px solid ' + COLORS["accent_green"] + '">'
        )
    else:
        photo_html = (
            '<div style="width:88px;height:88px;border-radius:50%;'
            'background:' + COLORS["surface"] + ';border:2px solid ' + COLORS["border"] + ';'
            'display:flex;align-items:center;justify-content:center;font-size:2rem">👤</div>'
        )
    logo_html = (
        '<img src="' + logo_url + '" style="width:30px;height:30px;object-fit:contain">'
        if logo_url else ""
    )
    badge_col = (
        COLORS["accent_green"] if dom_score >= 70 else
        COLORS["accent_gold"]  if dom_score >= 50 else
        COLORS["accent_red"]
    )
    badge_html = (
        '<span style="background:' + badge_col + '22;border:1px solid ' + badge_col + ';'
        'color:' + badge_col + ';border-radius:20px;padding:3px 10px;'
        'font-size:0.72rem;font-weight:700">'
        + dominant + ' · ' + f"{dom_score:.0f}" + '/100</span>'
        if dominant and dominant != "—" else ""
    )

    # KPIs
    kpi_row = ""
    if val_str != "—":
        kpi_row += _kpi_chip("Valeur", val_str, COLORS["accent_gold"])
    kpi_row += _kpi_chip("Buts",     fmt(r.get("Gls", "—"), 0), COLORS["accent_green"])
    kpi_row += _kpi_chip("Passes D", fmt(r.get("Ast", "—"), 0), COLORS["accent_blue"])
    kpi_row += _kpi_chip("xG",       fmt(r.get("xG", "—")),     COLORS["accent_gold"])
    kpi_row += _kpi_chip("Matchs",   fmt(r.get("MP", "—"), 0),  COLORS["text_muted"])
    kpi_row += _kpi_chip("Min",      fmt(r.get("Min", "—"), 0), COLORS["text_muted"])

    # Profil scores (barres)
    profile_bars = ""
    if all_scores:
        sorted_scores = sorted(all_scores.items(), key=lambda kv: kv[1], reverse=True)[:6]
        for prof, sc in sorted_scores:
            profile_bars += _pct_bar(prof, sc, bold=(prof == dominant))

    # Points forts / Axes d'amélioration HTML
    sw_left = ""   # strengths
    sw_right = ""  # weaknesses
    for p in strengths:
        text = _STRENGTH_PHRASES.get(p["metric"], "Top " + p["tag"] + " en " + p["metric"])
        sw_left += _sw_chip(text, True)
    for p in weaknesses:
        text = _WEAKNESS_PHRASES.get(p["metric"], p["metric"] + " (" + p["tag"] + ")")
        sw_right += _sw_chip(text, False)

    # Sections percentile — 2 colonnes (gauche / droite)
    left_sections = ""
    right_sections = ""
    SEC_SPLIT = 3   # 3 sections dans chaque colonne
    for i, (sec_title, items) in enumerate(rendered_sections):
        # Bold les 2 métriques avec les plus hauts percentiles dans chaque section
        sorted_items = sorted(items, key=lambda x: x["percentile"], reverse=True)
        top2 = {x["metric"] for x in sorted_items[:2]}
        bars = "".join(_pct_bar(it["metric"], it["percentile"], bold=(it["metric"] in top2)) for it in items)
        sec_html = _section_box(sec_title, bars)
        if i < SEC_SPLIT:
            left_sections += sec_html
        else:
            right_sections += sec_html

    # ── Assemblage identité (colonne gauche) ──────────────────────────────────
    identity_content = (
        '<div style="display:flex;align-items:center;gap:14px;margin-bottom:12px">'
        + photo_html +
        '<div style="flex:1">'
        '<div style="font-size:1.15rem;font-weight:800;color:' + COLORS["text"] + ';line-height:1.2">'
        + player + '</div>'
        '<div style="display:flex;align-items:center;gap:5px;margin-top:4px">'
        + logo_html +
        '<span style="font-size:0.78rem;color:' + COLORS["text_muted"] + '">' + team + '</span>'
        '</div>'
        '<div style="font-size:0.72rem;color:' + COLORS["text_muted"] + ';margin-top:3px">'
        + str(pos) + ' · ' + str(age) + ' ans'
        + (' · ' + nationality if nationality else '')
        + (' · ' + foot if foot else '') +
        '</div>'
        '<div style="font-size:0.7rem;color:' + COLORS["text_muted"] + ';margin-top:1px">'
        + league_label + ' · ' + season_label + '</div>'
        + ('<div style="margin-top:6px">' + badge_html + '</div>' if badge_html else '') +
        '</div>'
        '</div>'
        '<div style="display:flex;flex-wrap:wrap;gap:5px">' + kpi_row + '</div>'
    )

    left_col = (
        '<div style="flex:0 0 280px;min-width:240px">'
        + _card_box(identity_content)
        + (_card_box(
            '<div style="font-size:0.65rem;font-weight:700;color:' + COLORS["text_muted"] + ';'
            'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px">INDICES DE PROFIL</div>'
            + profile_bars
        ) if profile_bars else "")
        + (  # Similaires
            _card_box(
                '<div style="font-size:0.65rem;font-weight:700;color:' + COLORS["text_muted"] + ';'
                'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px">PROFILS SIMILAIRES</div>'
                + "".join(_similar_row(n, t, c) for n, t, c in sim_list)
            ) if sim_list else ""
        )
        + '</div>'
    )

    # ── Colonnes percentiles ──────────────────────────────────────────────────
    mid_col = (
        '<div style="flex:1;min-width:200px">'
        + (left_sections if left_sections else
           '<div style="color:' + COLORS["text_muted"] + ';font-size:0.85rem;padding:10px">'
           'Données de percentile insuffisantes.</div>')
        + '</div>'
    )
    right_col = (
        '<div style="flex:1;min-width:200px">'
        + right_sections
        + '</div>'
    ) if right_sections else ""

    # ── Points forts / Axes d'amélioration ──────────────────────────────────
    sw_row = ""
    if sw_left or sw_right:
        sw_row = (
            '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:6px">'
            + (
                '<div style="flex:1;min-width:200px">'
                '<div style="font-size:0.72rem;font-weight:700;color:' + COLORS["accent_green"] + ';'
                'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px">↗ POINTS FORTS</div>'
                + sw_left + '</div>'
                if sw_left else ""
            )
            + (
                '<div style="flex:1;min-width:200px">'
                '<div style="font-size:0.72rem;font-weight:700;color:' + COLORS["accent_red"] + ';'
                'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px">↘ AXES D\'AMÉLIORATION</div>'
                + sw_right + '</div>'
                if sw_right else ""
            )
            + '</div>'
        )

    st.markdown(
        '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif">'
        # Ligne principale
        '<div style="display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start">'
        + left_col + mid_col + right_col +
        '</div>'
        # Points forts / faiblesses
        + sw_row +
        '</div>',
        unsafe_allow_html=True,
    )


# ── Carte club ────────────────────────────────────────────────────────────────

# Sections club : mêmes principes, métriques adaptées
REPORT_SECTIONS_CLUB: list[tuple[str, dict[str, tuple[str, str]]]] = [
    ("OFFENSIF", {
        "Buts":                    ("standard",  "Gls"),
        "xG":                      ("shooting",  "xG"),
        "npxG":                    ("shooting",  "npxG"),
        "Tirs cadrés %":           ("shooting",  "SoT%"),
        "Passes décisives":        ("standard",  "Ast"),
        "xAG":                     ("passing",   "xAG"),
    }),
    ("CRÉATION", {
        "Actions créatrices":      ("goal_shot_creation", "SCA"),
        "Actions décisives":       ("goal_shot_creation", "GCA"),
        "Passes clés":             ("passing",            "KP"),
        "Passes dernier tiers":    ("passing",            "1/3"),
        "Passes vers la surface":  ("passing",            "PPA"),
        "Centres réussis":         ("passing",            "CrsPA"),
    }),
    ("POSSESSION", {
        "Possession %":            ("standard",   "Poss"),
        "Passes réussies %":       ("passing",    "Cmp%"),
        "Passes progressives":     ("passing",    "PrgP"),
        "Courses progressives":    ("standard",   "PrgC"),
        "Distance progressive":    ("passing",    "PrgDist"),
    }),
    ("DÉFENSIF", {
        "Tacles":                  ("defense",    "Tkl"),
        "Tacles gagnés":           ("defense",    "TklW"),
        "Interceptions":           ("defense",    "Int"),
        "Blocs":                   ("defense",    "Blocks"),
        "Dégagements":             ("defense",    "Clr"),
    }),
    ("PRESSING", {
        "Récupérations":           ("misc",       "Recov"),
        "Duels aériens gagnés %":  ("misc",       "Won%"),
        "Fautes subies":           ("misc",       "Fld"),
    }),
]


def render_club_report_card(
    team: str,
    season: str,
    league_filter: str | None,
) -> None:
    from data.loader import load_team_season_stats
    from data.processor import (
        build_percentiles_labeled,
        build_performance_index,
        find_similar_teams,
    )
    from config import METRICS_WITH_BALL, METRICS_WITHOUT_BALL

    try:
        from transfermarkt.matcher import (
            match_club, format_value, get_club_logo, get_squad_value_season,
        )
    except Exception:
        def match_club(*a, **kw): return None
        def format_value(v): return "—"
        def get_club_logo(*a, **kw): return None
        def get_squad_value_season(*a, **kw): return None

    season_label = SEASONS.get(season, season)
    league_label = LEAGUE_LABELS.get(league_filter, league_filter or "Big 5")

    std = load_team_season_stats("standard", [season])
    if league_filter:
        std = std[std["league"] == league_filter]
    row = std[std["team"] == team]
    if row.empty:
        st.warning("Données insuffisantes pour générer la carte.")
        return
    r = row.iloc[0]

    def fmt(v, d=1):
        try:
            return f"{float(v):.{d}f}"
        except Exception:
            return "—"

    logo_url  = get_club_logo(team, league_filter) or ""
    squad_val = get_squad_value_season(team, season, league_filter)
    val_str   = format_value(squad_val) if squad_val else "—"

    # Percentiles par section
    all_pct: dict[str, dict] = {}
    rendered_sections: list[tuple[str, list[dict]]] = []
    for sec_title, metrics_dict in REPORT_SECTIONS_CLUB:
        items = build_percentiles_labeled(metrics_dict, team, "team", season, league_filter)
        if items:
            for item in items:
                all_pct[item["metric"]] = item
            rendered_sections.append((sec_title, items))

    by_pct     = sorted(all_pct.values(), key=lambda x: x["percentile"], reverse=True)
    strengths  = [p for p in by_pct if p["percentile"] >= 75][:4]
    weaknesses = sorted([p for p in by_pct if p["percentile"] <= 30], key=lambda x: x["percentile"])[:4]

    # Indices de performance
    try:
        idx_df   = build_performance_index([team], season, league_filter)
        idx_rows = (
            idx_df[idx_df["team"] == team][["index", "score"]].values.tolist()
            if not idx_df.empty and "index" in idx_df.columns else []
        )
    except Exception:
        idx_rows = []

    # Équipes similaires
    try:
        sim = find_similar_teams(team, season, league_filter, n=3)
        sim_list = sim[["team", "league", "compat_pct"]].values.tolist() if not sim.empty else []
    except Exception:
        sim_list = []

    # HTML
    if logo_url:
        logo_html = (
            '<img src="' + logo_url + '" style="width:76px;height:76px;object-fit:contain;'
            'border-radius:8px;border:2px solid ' + COLORS["border"] + '">'
        )
    else:
        logo_html = (
            '<div style="width:76px;height:76px;border-radius:8px;'
            'background:' + COLORS["surface"] + ';border:2px solid ' + COLORS["border"] + ';'
            'display:flex;align-items:center;justify-content:center;font-size:2rem">🏟️</div>'
        )

    kpi_row = ""
    if val_str != "—":
        kpi_row += _kpi_chip("Valeur effectif", val_str, COLORS["accent_gold"])
    kpi_row += _kpi_chip("Buts",       fmt(r.get("Gls", "—"), 0), COLORS["accent_green"])
    kpi_row += _kpi_chip("xG",         fmt(r.get("xG", "—")),     COLORS["accent_gold"])
    kpi_row += _kpi_chip("Possession", fmt(r.get("Poss", "—")) + "%", COLORS["accent_blue"])
    kpi_row += _kpi_chip("PrgP",       fmt(r.get("PrgP", "—"), 0), COLORS["text_muted"])

    idx_bars = "".join(_pct_bar(str(n), float(s), bold=False) for n, s in idx_rows if s is not None)

    # Sections
    left_sections = ""
    right_sections = ""
    SEC_SPLIT = 3
    for i, (sec_title, items) in enumerate(rendered_sections):
        sorted_items = sorted(items, key=lambda x: x["percentile"], reverse=True)
        top2 = {x["metric"] for x in sorted_items[:2]}
        bars = "".join(_pct_bar(it["metric"], it["percentile"], bold=(it["metric"] in top2)) for it in items)
        sec_html = _section_box(sec_title, bars)
        if i < SEC_SPLIT:
            left_sections += sec_html
        else:
            right_sections += sec_html

    identity_content = (
        '<div style="display:flex;align-items:center;gap:14px;margin-bottom:12px">'
        + logo_html +
        '<div>'
        '<div style="font-size:1.2rem;font-weight:800;color:' + COLORS["text"] + '">' + team + '</div>'
        '<div style="font-size:0.75rem;color:' + COLORS["text_muted"] + ';margin-top:3px">'
        + league_label + ' · ' + season_label + '</div>'
        '</div>'
        '</div>'
        '<div style="display:flex;flex-wrap:wrap;gap:5px">' + kpi_row + '</div>'
    )

    left_col = (
        '<div style="flex:0 0 280px;min-width:240px">'
        + _card_box(identity_content)
        + (_card_box(
            '<div style="font-size:0.65rem;font-weight:700;color:' + COLORS["text_muted"] + ';'
            'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px">INDICES COMPOSITES</div>'
            + idx_bars
        ) if idx_bars else "")
        + (
            _card_box(
                '<div style="font-size:0.65rem;font-weight:700;color:' + COLORS["text_muted"] + ';'
                'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px">STYLE SIMILAIRE</div>'
                + "".join(_similar_row(n, lg, c) for n, lg, c in sim_list)
            ) if sim_list else ""
        )
        + '</div>'
    )

    mid_col = (
        '<div style="flex:1;min-width:200px">'
        + (left_sections if left_sections else
           '<div style="color:' + COLORS["text_muted"] + ';font-size:0.85rem;padding:10px">'
           'Données insuffisantes.</div>')
        + '</div>'
    )
    right_col = (
        '<div style="flex:1;min-width:200px">' + right_sections + '</div>'
        if right_sections else ""
    )

    # Points forts / Axes
    sw_left  = "".join(_sw_chip(p["metric"] + " (" + p["tag"] + ")", True) for p in strengths)
    sw_right = "".join(_sw_chip(p["metric"] + " (" + p["tag"] + ")", False) for p in weaknesses)
    sw_row = ""
    if sw_left or sw_right:
        sw_row = (
            '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:6px">'
            + (
                '<div style="flex:1;min-width:200px">'
                '<div style="font-size:0.72rem;font-weight:700;color:' + COLORS["accent_green"] + ';'
                'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px">↗ POINTS FORTS</div>'
                + sw_left + '</div>' if sw_left else ""
            )
            + (
                '<div style="flex:1;min-width:200px">'
                '<div style="font-size:0.72rem;font-weight:700;color:' + COLORS["accent_red"] + ';'
                'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px">↘ AXES D\'AMÉLIORATION</div>'
                + sw_right + '</div>' if sw_right else ""
            )
            + '</div>'
        )

    st.markdown(
        '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif">'
        '<div style="display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start">'
        + left_col + mid_col + right_col +
        '</div>'
        + sw_row +
        '</div>',
        unsafe_allow_html=True,
    )
