"""
Dashboard Couverture — visualisation de l'état d'extraction.
Matrice saison × type de fichier, taille MB, nombre de lignes, dates.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from config import (
    BASE_DIR, COLORS, SEASONS, _ALL_SEASONS,
    TEAM_SEASON_STATS, PLAYER_SEASON_STATS,
    TEAM_MATCH_STATS, PLAYER_MATCH_STATS,
)
from components.kpi_cards import render_section_header, render_kpi_row


# Catégories de fichiers attendus
CATEGORIES = {
    "Stats équipe (saison)":  [f"FB_team_season_stats_{s}.csv"   for s in TEAM_SEASON_STATS],
    "Stats joueur (saison)":  [f"FB_player_season_stats_{s}.csv" for s in PLAYER_SEASON_STATS],
    "Stats équipe (par match)":  [f"FB_team_match_stats_{s}.csv"   for s in TEAM_MATCH_STATS],
    "Stats joueur (par match)":  [f"FB_player_match_stats_{s}.csv" for s in PLAYER_MATCH_STATS],
    "Calendrier & événements":   ["FB_schedule.csv", "FB_lineups.csv", "FB_events.csv"],
}

# Stat_types récupérables avec soccerdata 1.9.0
SD_19_OK = {
    "FB_team_season_stats_": {"standard", "keeper", "shooting", "playing_time", "misc"},
    "FB_player_season_stats_": {"standard", "keeper", "shooting", "playing_time", "misc"},
    "FB_team_match_stats_":   {"shooting", "keeper", "misc"},
    "FB_player_match_stats_": {"summary", "keepers"},
}


def _is_supported_by_19(filename: str) -> bool:
    for prefix, allowed in SD_19_OK.items():
        if filename.startswith(prefix):
            stat = filename[len(prefix):-len(".csv")]
            return stat in allowed
    return True  # schedule, lineups, events : OK


def _file_info(path: Path) -> dict | None:
    if not path.exists():
        return None
    stat = path.stat()
    try:
        # Lecture rapide du nombre de lignes
        with open(path, "rb") as f:
            n = sum(1 for _ in f) - 1
    except Exception:
        n = -1
    return {
        "size_mb": round(stat.st_size / 1e6, 2),
        "rows":    n,
        "mtime":   pd.Timestamp(stat.st_mtime, unit="s"),
    }


def render() -> None:
    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin-bottom:0'>🗂️ Couverture des données</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:14px'>"
        f"État d'extraction par saison · soccerdata + Transfermarkt</div>",
        unsafe_allow_html=True,
    )

    # ── KPIs globaux ─────────────────────────────────────────────────────────
    all_seasons = list(_ALL_SEASONS.keys())
    total_expected = sum(len(v) for v in CATEGORIES.values()) * len(all_seasons)
    total_present  = 0
    total_size_mb  = 0.0
    total_rows     = 0
    for s in all_seasons:
        for files in CATEGORIES.values():
            for f in files:
                p = BASE_DIR / s / f
                info = _file_info(p)
                if info:
                    total_present += 1
                    total_size_mb += info["size_mb"]
                    total_rows    += max(info["rows"], 0)

    pct = 100 * total_present / total_expected if total_expected else 0
    render_kpi_row([
        {"label": "Saisons détectées", "value": f"{len(SEASONS)}/{len(all_seasons)}",
         "color": COLORS["accent_green"]},
        {"label": "Fichiers présents", "value": f"{total_present}/{total_expected}",
         "color": COLORS["accent_blue"]},
        {"label": "Couverture",         "value": f"{pct:.0f}%",
         "color": COLORS["accent_gold"]},
        {"label": "Taille totale",      "value": f"{total_size_mb:.0f} MB",
         "color": COLORS["accent_red"]},
        {"label": "Lignes totales",     "value": f"{total_rows:,}".replace(",", " "),
         "color": COLORS["text_muted"]},
    ])

    # ── Matrice saisons × fichiers par catégorie ─────────────────────────────
    for cat_name, files in CATEGORIES.items():
        render_section_header(cat_name, f"{len(files)} fichier(s) attendu(s) par saison")

        # Construction matrice : lignes = fichiers, colonnes = saisons
        rows = []
        for f in files:
            stat_label = (
                f.replace("FB_team_season_stats_", "")
                 .replace("FB_player_season_stats_", "")
                 .replace("FB_team_match_stats_", "")
                 .replace("FB_player_match_stats_", "")
                 .replace("FB_", "")
                 .replace(".csv", "")
            )
            sd_ok = "✅" if _is_supported_by_19(f) else "⚠️"
            row = {"Fichier": stat_label, "SD 1.9": sd_ok}
            for s in all_seasons:
                p = BASE_DIR / s / f
                info = _file_info(p)
                if info:
                    row[_ALL_SEASONS[s]] = f"✓ {info['size_mb']:.1f}MB"
                else:
                    row[_ALL_SEASONS[s]] = "—"
            rows.append(row)

        df = pd.DataFrame(rows)
        st.dataframe(
            df, use_container_width=True, hide_index=True,
            height=min(40 * len(rows) + 50, 600),
        )

    st.divider()
    st.markdown(
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem'>"
        f"<b>Légende</b> · ✅ = stat_type supporté par soccerdata 1.9.0 · "
        f"⚠️ = nécessite soccerdata ≤ 1.8.7 (downgrade : "
        f"<code>pip install \"soccerdata==1.8.7\"</code>)<br/>"
        f"<b>Méthodes FBref disponibles (1.9.0)</b> · "
        f"<code>read_team_season_stats</code> (standard, keeper, shooting, playing_time, misc) · "
        f"<code>read_team_match_stats</code> (shooting, keeper, misc) · "
        f"<code>read_player_season_stats</code> (standard, keeper, shooting, playing_time, misc) · "
        f"<code>read_player_match_stats</code> (summary, keepers) · "
        f"<code>read_schedule</code> · <code>read_lineup</code> · <code>read_events</code>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Détail par saison (expandeurs) ───────────────────────────────────────
    render_section_header("Détail par saison", "Liste complète des fichiers présents")
    for s in all_seasons:
        folder = BASE_DIR / s
        if not folder.exists():
            with st.expander(f"📂 {_ALL_SEASONS[s]} — dossier absent", expanded=False):
                st.warning(f"Le dossier `{s}/` n'existe pas.")
            continue

        files = sorted(folder.glob("FB_*.csv"))
        with st.expander(
            f"📂 {_ALL_SEASONS[s]} — {len(files)} fichier(s)",
            expanded=False,
        ):
            if not files:
                st.info("Aucun fichier FB_*.csv.")
                continue
            data = []
            for p in files:
                info = _file_info(p)
                data.append({
                    "Fichier": p.name,
                    "Lignes":   info["rows"] if info else 0,
                    "Taille":   f"{info['size_mb']:.2f} MB" if info else "—",
                    "Modifié":  info["mtime"].strftime("%Y-%m-%d %H:%M") if info else "—",
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True,
                         height=min(36 * len(data) + 50, 500))
