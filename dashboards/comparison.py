"""
Dashboard Comparaison.
Tabs : Équipes (scatter xG/xGA) | Joueurs (radar 2 joueurs) | SHAP | Prédiction PPM
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from config import COLORS, PLAYER_METRICS_BY_POS, LEAGUE_LABELS, LEAGUES
from components.charts import make_scatter, make_radar, make_percentile_bars
from components.filters import select_two_players
from components.glossary import (
    render_metric_glossary, render_disclaimer,
    watchlist_get, watchlist_remove, watchlist_clear,
)
from components.kpi_cards import render_section_header, render_kpi_row
from data.loader import (
    load_team_season_stats, load_player_season_stats, load_all_team_season_stats,
)
from data.processor import percentile_score, build_radar_data

try:
    from transfermarkt.matcher import (
        match_player, get_club_logo, format_value,
        enrich_with_logos, enrich_with_photos,
    )
    TM_AVAILABLE = True
except Exception:
    TM_AVAILABLE = False
    def match_player(*a, **kw): return None
    def get_club_logo(*a, **kw): return None
    def format_value(v): return "—"
    def enrich_with_logos(df, *a, **kw): return df
    def enrich_with_photos(df, *a, **kw): return df


def _player_card(player: str, team: str, league_filter: str | None) -> None:
    """Mini-fiche joueur avec photo + logo club."""
    tm = match_player(player, fbref_league=league_filter)
    photo = tm.get("image_url") if tm else None
    logo = get_club_logo(team, league_filter)
    mv = tm.get("market_value_in_eur") if tm else None

    cols = st.columns([1, 1, 6])
    with cols[0]:
        if photo: st.image(photo, width=70)
    with cols[1]:
        if logo: st.image(logo, width=50)
    with cols[2]:
        st.markdown(
            f"<div style='padding-top:6px'>"
            f"<div style='font-size:1.1rem;font-weight:800;color:{COLORS['text']}'>{player}</div>"
            f"<div style='font-size:0.82rem;color:{COLORS['text_muted']}'>"
            f"{team}{' · ' + format_value(mv) if mv and pd.notna(mv) else ''}"
            f"</div></div>",
            unsafe_allow_html=True,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pos_group(pos_str: str) -> str:
    if pd.isna(pos_str):
        return "MF"
    pos = str(pos_str).upper()
    if "GK" in pos:
        return "GK"
    if "FW" in pos:
        return "FW"
    if "DF" in pos:
        return "DF"
    return "MF"


def _player_percentiles(
    player: str, team: str,
    metrics: list[tuple[str, str]],
    season: str, league: str | None,
    pos_group: str,
    min_minutes: int = 500,
) -> tuple[list[str], list[float], list[float]]:
    """
    Renvoie (labels, percentiles 0-100, valeurs brutes) pour un joueur,
    en comparant aux joueurs de même position (≥ min_minutes).
    """
    from data.processor import percentile_score

    labels, percentiles, raw = [], [], []
    std = load_player_season_stats("standard", [season])
    if league:
        std = std[std["league"] == league]

    for stat_type, col in metrics:
        df = load_player_season_stats(stat_type, [season])
        if league:
            df = df[df["league"] == league]
        if col not in df.columns:
            continue

        # Filtrer même position + minutes minimum via merge sur (player, team)
        if "Min" in std.columns and "pos" in std.columns:
            ref = std[["player", "team", "pos", "Min"]].copy()
            ref["Min"] = pd.to_numeric(ref["Min"], errors="coerce")
            ref = ref[ref["Min"] >= min_minutes]
            ref = ref[ref["pos"].apply(_pos_group) == pos_group]
            df = df.merge(ref[["player", "team"]], on=["player", "team"], how="inner")

        series = pd.to_numeric(df[col], errors="coerce")
        row = df[(df["player"] == player) & (df["team"] == team)]
        if row.empty:
            continue
        val = pd.to_numeric(row[col].values[0], errors="coerce")
        if pd.isna(val):
            continue
        pct = percentile_score(series, float(val))
        labels.append(col)
        percentiles.append(pct)
        raw.append(float(val))
    return labels, percentiles, raw


# ── Render ────────────────────────────────────────────────────────────────────

def render(season: str, league: str) -> None:
    league_filter = None if league == "Toutes les ligues" else league

    tab1, tab2, tab_wl, tab3, tab4 = st.tabs([
        "🏟️ Équipes",
        "👥 Joueurs",
        "📋 Ma shortlist",
        "🔍 SHAP",
        "🏆 Prédiction PPM",
    ])

    # ── Tab 1 : Scatter xG vs xGA équipes ────────────────────────────────────
    with tab1:
        render_section_header(
            "xG vs xGA — Toutes les équipes",
            "Axe X = danger créé · Axe Y = danger concédé · Point bas-droit = meilleur profil.",
        )

        std = load_team_season_stats("standard", [season])
        sht = load_team_season_stats("shooting", [season])
        if league_filter:
            std = std[std["league"] == league_filter]
            sht = sht[sht["league"] == league_filter]

        merged = std[["team", "league", "Poss"]].merge(
            sht[["team", "xG", "npxG"]], on="team", how="inner"
        )

        # On récupère xGA depuis keeper
        kpr = load_team_season_stats("keeper", [season])
        if league_filter:
            kpr = kpr[kpr["league"] == league_filter]
        if "GA" in kpr.columns:
            merged = merged.merge(kpr[["team", "GA"]], on="team", how="left")
            merged = merged.rename(columns={"GA": "xGA"})
        elif "GA90" in kpr.columns:
            merged = merged.merge(kpr[["team", "GA90"]], on="team", how="left")
            merged = merged.rename(columns={"GA90": "xGA"})

        if "xGA" not in merged.columns or merged.empty:
            st.info("Données xGA insuffisantes.")
        else:
            for c in ["xG", "xGA", "Poss"]:
                if c in merged.columns:
                    merged[c] = pd.to_numeric(merged[c], errors="coerce")

            fig = make_scatter(
                merged.dropna(subset=["xG", "xGA"]),
                x="xG", y="xGA",
                text="team",
                size="Poss" if "Poss" in merged.columns else None,
                title=f"xG vs xGA — {league_filter or 'Big 5'} · {season}",
                xlab="xG (danger créé)", ylab="xGA (danger concédé)",
                highlight=merged["team"].tolist(),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Tableau classement
        render_section_header("Tableau de bord ligue")
        if not merged.empty:
            show = merged.sort_values("xG", ascending=False)
            show = enrich_with_logos(show, team_col="team", league=league_filter)

            order = []
            if "logo_url" in show.columns: order.append("logo_url")
            order += ["team", "league", "xG", "npxG", "xGA", "Poss"]
            display_cols = [c for c in order if c in show.columns]

            disp = show[display_cols].reset_index(drop=True).rename(columns={
                "logo_url": "Logo", "team": "Équipe", "league": "Ligue",
            })
            column_config = {}
            if "Logo" in disp.columns:
                column_config["Logo"] = st.column_config.ImageColumn("Logo", width="small")
            for c in ["xG", "npxG", "xGA", "Poss"]:
                if c in disp.columns:
                    column_config[c] = st.column_config.NumberColumn(c, format="%.2f")
            st.dataframe(
                disp, use_container_width=True, hide_index=True, column_config=column_config,
            )
            render_metric_glossary(metrics=["xG", "npxG", "xGA", "Poss"])

    # ── Tab 2 : Comparaison joueurs ───────────────────────────────────────────
    with tab2:
        render_section_header(
            "Comparaison radar — 2 joueurs",
            "Sélectionnez deux joueurs de même position pour une comparaison équitable.",
        )

        pdf = load_player_season_stats("standard", [season])
        if league_filter:
            pdf = pdf[pdf["league"] == league_filter]

        (p1, t1), (p2, t2) = select_two_players(season, league)
        if not (p1 and p2):
            st.info("Sélectionnez deux joueurs.")
        else:
            # Cartes joueurs avec photos + logos
            cardA, cardB = st.columns(2)
            with cardA: _player_card(p1, t1, league_filter)
            with cardB: _player_card(p2, t2, league_filter)

            # Position de référence : celle du joueur 1
            row1 = pdf[(pdf["player"] == p1) & (pdf["team"] == t1)]
            pos1 = _pos_group(row1["pos"].values[0] if not row1.empty else "MF")
            row2 = pdf[(pdf["player"] == p2) & (pdf["team"] == t2)]
            pos2 = _pos_group(row2["pos"].values[0] if not row2.empty else "MF")

            if pos1 != pos2:
                st.warning(
                    f"⚠️ Positions différentes : {p1} ({pos1}) vs {p2} ({pos2}). "
                    f"La comparaison utilise les métriques du poste de **{p1}**."
                )
            metrics = PLAYER_METRICS_BY_POS.get(pos1, PLAYER_METRICS_BY_POS["MF"])

            l1, p_pct1, r1 = _player_percentiles(p1, t1, metrics, season, league_filter, pos1)
            l2, p_pct2, r2 = _player_percentiles(p2, t2, metrics, season, league_filter, pos1)

            common = [l for l in l1 if l in l2]
            if not common:
                st.warning("Pas de métriques communes pour ces joueurs.")
            else:
                # Radar percentiles (0-100 → 0-1 pour cohérence visuelle)
                idx1 = {l: i for i, l in enumerate(l1)}
                idx2 = {l: i for i, l in enumerate(l2)}
                fig = make_radar(
                    {
                        p1: [p_pct1[idx1[l]] / 100 for l in common],
                        p2: [p_pct2[idx2[l]] / 100 for l in common],
                    },
                    common,
                    title=f"Comparaison percentile — joueurs {pos1} (≥ 500 min)",
                )
                st.plotly_chart(fig, use_container_width=True)

                # Tableau côte-à-côte : valeurs brutes + percentile
                comp_df = pd.DataFrame({
                    "Métrique": common,
                    f"{p1} · valeur": [round(r1[idx1[l]], 2) for l in common],
                    f"{p1} · percentile": [round(p_pct1[idx1[l]], 0) for l in common],
                    f"{p2} · valeur": [round(r2[idx2[l]], 2) for l in common],
                    f"{p2} · percentile": [round(p_pct2[idx2[l]], 0) for l in common],
                })
                comp_df["Δ percentile"] = comp_df[f"{p1} · percentile"] - comp_df[f"{p2} · percentile"]
                st.dataframe(comp_df, use_container_width=True, hide_index=True)

                render_metric_glossary(metrics=common)

    # ── Tab Watchlist : ma shortlist personnelle ────────────────────────────
    with tab_wl:
        _render_watchlist_tab(season, league_filter)

    # ── Tab 3 : SHAP ──────────────────────────────────────────────────────────
    with tab3:
        render_section_header(
            "Analyse SHAP — Random Forest",
            "Importance des métriques pour prédire le niveau de la ligue (xG équipe).",
        )

        if st.button("Lancer l'analyse SHAP", key="shap_btn"):
            with st.spinner("Entraînement du modèle…"):
                try:
                    import shap
                    from sklearn.ensemble import RandomForestRegressor

                    stat_types = ["standard", "shooting", "passing", "defense",
                                  "possession", "goal_shot_creation", "misc"]
                    dfs = load_all_team_season_stats(stat_types)

                    base = dfs["standard"][["league", "season", "team", "Poss"]].copy()
                    target_col = "xG"
                    sht = dfs["shooting"]
                    if target_col not in sht.columns:
                        st.warning("Colonne xG introuvable.")
                        st.stop()

                    base = base.merge(sht[["team", "season", "league", target_col]], on=["team", "season", "league"], how="inner")

                    for st_name, df in dfs.items():
                        if st_name in ("standard", "shooting"):
                            continue
                        skip = {"league", "season", "team", "url"}
                        num_cols = [c for c in df.columns if c not in skip]
                        sub = df[["team", "season", "league"] + num_cols].copy()
                        base = base.merge(sub, on=["team", "season", "league"], how="left", suffixes=("", f"_{st_name}"))

                    drop_kw = {"Rank", "Gls", "GA", "PK", "Save%", "CS", "onxG", "OG", "url"}
                    feat_cols = [
                        c for c in base.columns
                        if c not in {"league", "season", "team", target_col}
                        and not any(k in c for k in drop_kw)
                    ]
                    X = base[feat_cols].apply(pd.to_numeric, errors="coerce")
                    y = pd.to_numeric(base[target_col], errors="coerce")
                    mask = y.notna() & X.notna().all(axis=1)
                    X, y = X[mask], y[mask]

                    thresh = 0.5
                    valid_cols = X.columns[X.isna().mean() < thresh]
                    X = X[valid_cols].fillna(X[valid_cols].median())

                    rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
                    rf.fit(X, y)

                    explainer = shap.TreeExplainer(rf)
                    shap_vals = explainer.shap_values(X)

                    mean_abs = np.abs(shap_vals).mean(axis=0)
                    shap_df = pd.DataFrame({"feature": X.columns, "importance": mean_abs})
                    shap_df = shap_df.sort_values("importance", ascending=False).head(20)

                    import plotly.graph_objects as go
                    fig = go.Figure(go.Bar(
                        x=shap_df["importance"],
                        y=shap_df["feature"],
                        orientation="h",
                        marker_color=COLORS["accent_green"],
                    ))
                    from config import PLOTLY_LAYOUT
                    fig.update_layout(
                        **PLOTLY_LAYOUT,
                        title="Top 20 features — impact SHAP moyen",
                        yaxis=dict(autorange="reversed"),
                        height=520,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                except ImportError:
                    st.error("Installez `shap` : `pip install shap`")
                except Exception as e:
                    st.error(f"Erreur SHAP : {e}")

    # ── Tab 4 : Prédiction PPM ────────────────────────────────────────────────
    with tab4:
        render_section_header(
            "Prédiction classement — Points Par Match",
            "XGBoost entraîné sur les saisons passées, prédit le PPM de la saison courante.",
        )

        target_season = st.selectbox("Saison à prédire", list(
            reversed([s for s in (load_team_season_stats("playing_time")["season"].dropna().unique() if not load_team_season_stats("playing_time").empty else [])])
        ), key="ppm_season")

        if st.button("Lancer la prédiction PPM", key="ppm_btn"):
            with st.spinner("Entraînement XGBoost…"):
                try:
                    import xgboost as xgb

                    pt = load_team_season_stats("playing_time")
                    if "PPM" not in pt.columns and "PPM_playing_time" not in pt.columns:
                        possible = [c for c in pt.columns if "PPM" in c or "ppm" in c.lower()]
                        if not possible:
                            st.warning("Colonne PPM introuvable dans playing_time. Vérifiez les données.")
                            st.stop()
                        ppm_col = possible[0]
                    else:
                        ppm_col = "PPM" if "PPM" in pt.columns else "PPM_playing_time"

                    stat_types = ["standard", "shooting", "passing", "defense",
                                  "possession", "goal_shot_creation", "misc"]
                    dfs = load_all_team_season_stats(stat_types)
                    base = pt[["league", "season", "team", ppm_col]].copy()

                    for st_name, df in dfs.items():
                        skip = {"league", "season", "team", "url"}
                        num_cols = [c for c in df.columns if c not in skip]
                        sub = df[["team", "season", "league"] + num_cols].copy()
                        base = base.merge(sub, on=["team", "season", "league"], how="left", suffixes=("", f"_{st_name}"))

                    drop_kw = {"Rank", "Gls", "GA", "PK", "Save%", "CS", "onxG", "OG", "url", ppm_col}
                    feat_cols = [
                        c for c in base.columns
                        if c not in {"league", "season", "team", ppm_col}
                        and not any(k in c for k in drop_kw)
                    ]

                    X = base[feat_cols].apply(pd.to_numeric, errors="coerce")
                    y = pd.to_numeric(base[ppm_col], errors="coerce")

                    thresh = 0.5
                    valid_cols = X.columns[X.isna().mean() < thresh]
                    X = X[valid_cols]

                    train_mask = (base["season"] != target_season) & y.notna() & X.notna().all(axis=1)
                    pred_mask  = (base["season"] == target_season) & X.notna().all(axis=1)

                    X_train = X[train_mask].fillna(X[train_mask].median())
                    y_train = y[train_mask]
                    X_pred  = X[pred_mask].fillna(X[train_mask].median())

                    if len(X_train) < 5:
                        st.warning("Pas assez de données d'entraînement.")
                        st.stop()

                    model = xgb.XGBRegressor(n_estimators=200, learning_rate=0.05,
                                             max_depth=4, random_state=42,
                                             verbosity=0)
                    model.fit(X_train, y_train)
                    preds = model.predict(X_pred)

                    result_df = base[pred_mask][["league", "team"]].copy()
                    result_df["PPM_prédit"] = preds.round(3)
                    result_df["Rang_prédit"] = result_df.groupby("league")["PPM_prédit"].rank(ascending=False).astype(int)
                    result_df = result_df.sort_values(["league", "Rang_prédit"])

                    for lg in result_df["league"].unique():
                        render_section_header(LEAGUE_LABELS.get(lg, lg))
                        sub = result_df[result_df["league"] == lg][["Rang_prédit", "team", "PPM_prédit"]]
                        st.dataframe(
                            sub.reset_index(drop=True)
                            .style.format({"PPM_prédit": "{:.3f}"}),
                            use_container_width=True,
                        )

                except ImportError:
                    st.error("Installez `xgboost` : `pip install xgboost`")
                except Exception as e:
                    st.error(f"Erreur prédiction : {e}")

    render_disclaimer()


# ── Watchlist ────────────────────────────────────────────────────────────────

def _render_watchlist_tab(season: str, league_filter: str | None) -> None:
    render_section_header(
        "Ma shortlist",
        "Liste personnelle de joueurs à suivre. Ajoute-les depuis la page Profil "
        "Joueur (bouton ☆), puis compare-les ici.",
    )

    wl = watchlist_get()
    if not wl:
        st.info(
            "Ta shortlist est vide. Va sur **👤 Profil Joueur**, sélectionne un "
            "joueur et clique sur **☆ Ajouter à ma shortlist**."
        )
        return

    # Récupérer les stats pour les joueurs de la watchlist
    df_wl = pd.DataFrame(wl)

    pdf = load_player_season_stats("standard", [season])
    if league_filter:
        pdf = pdf[pdf["league"] == league_filter]

    enriched = df_wl.merge(
        pdf[["player", "team", "league", "pos", "age", "Gls", "Ast"]],
        on=["player", "team"], how="left", suffixes=("_wl", ""),
    )

    enriched = enrich_with_photos(enriched, player_col="player", league=league_filter)
    enriched = enrich_with_logos(enriched, team_col="team", league=league_filter)

    if "market_value_in_eur" in enriched.columns:
        enriched["Valeur"] = enriched["market_value_in_eur"].apply(format_value)

    cols = []
    if "image_url" in enriched.columns: cols.append("image_url")
    cols += ["player"]
    if "logo_url" in enriched.columns: cols.append("logo_url")
    cols += ["team", "league", "pos", "age", "Gls", "Ast"]
    if "Valeur" in enriched.columns: cols.append("Valeur")

    disp = enriched[[c for c in cols if c in enriched.columns]].rename(columns={
        "image_url": "Photo", "logo_url": "Logo",
        "player": "Joueur", "team": "Équipe", "league": "Ligue",
        "pos": "Position", "age": "Âge",
        "Gls": "Buts", "Ast": "Passes D.",
    })

    column_config = {}
    if "Photo" in disp.columns:
        column_config["Photo"] = st.column_config.ImageColumn("Photo", width="small")
    if "Logo" in disp.columns:
        column_config["Logo"] = st.column_config.ImageColumn("Logo", width="small")

    st.dataframe(
        disp, use_container_width=True, hide_index=True,
        height=min(60 * len(disp) + 50, 700),
        column_config=column_config,
    )

    # Actions : retirer un joueur, vider la shortlist
    st.divider()
    cA, cB = st.columns([3, 1])
    with cA:
        names = [f"{w['player']} — {w['team']}" for w in wl]
        to_remove = st.selectbox("Retirer un joueur", ["—"] + names, key="wl_remove")
        if to_remove != "—" and st.button("🗑️ Retirer", key="wl_remove_btn"):
            idx = names.index(to_remove)
            watchlist_remove(wl[idx]["player"], wl[idx]["team"])
            st.rerun()
    with cB:
        if st.button("🧹 Vider la shortlist", key="wl_clear", type="secondary",
                     use_container_width=True):
            watchlist_clear()
            st.rerun()

    st.caption(
        f"💡 {len(wl)} joueur(s) en shortlist · La sélection persiste tant que la "
        f"session est ouverte."
    )
