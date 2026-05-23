"""
Factories de graphiques Plotly réutilisables.
Toutes les fonctions retournent un go.Figure avec le thème sombre ElevenField.
Pour ajouter un type de graphique : créer une nouvelle fonction make_* ici.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from config import COLORS, PLOTLY_LAYOUT, TEAM_COLORS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _base_layout(**overrides) -> dict:
    """
    Merge PLOTLY_LAYOUT defaults with overrides.
    Override keys (margin, legend, etc.) replace the defaults so callers
    can safely pass them without ``multiple values for keyword`` errors.
    """
    layout = {**PLOTLY_LAYOUT}
    layout.update(overrides)
    return layout


def _safe_update(fig: go.Figure, **kwargs) -> None:
    """update_layout en évitant les doublons de clés (margin/legend/...)."""
    layout = {**PLOTLY_LAYOUT}
    layout.update(kwargs)
    fig.update_layout(**layout)


def _rgba(hex_color: str, alpha: float = 0.3) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ── Radar ─────────────────────────────────────────────────────────────────────

def make_radar(
    teams_data: dict[str, list[float]],
    categories: list[str],
    title: str = "",
    colors: list[str] | None = None,
) -> go.Figure:
    """
    Radar chart comparatif.
    teams_data : {nom_equipe: [valeurs normalisées 0-1]}
    categories : liste des labels de métriques
    """
    if colors is None:
        colors = TEAM_COLORS

    fig = go.Figure()
    cats = categories + [categories[0]]  # fermer le polygone

    for i, (name, values) in enumerate(teams_data.items()):
        color = colors[i % len(colors)]
        vals = list(values) + [values[0]]
        fig.add_trace(go.Scatterpolar(
            r=vals,
            theta=cats,
            fill="toself",
            fillcolor=_rgba(color, 0.25),
            line=dict(color=color, width=2.5),
            name=name,
            hovertemplate="%{theta}: %{r:.2f}<extra>" + name + "</extra>",
        ))

    fig.update_layout(
        **_base_layout(title=dict(text=title, font=dict(size=16, color=COLORS["text"]))),
        polar=dict(
            bgcolor=COLORS["surface"],
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                showticklabels=False,
                gridcolor=COLORS["grid"],
                linecolor=COLORS["grid"],
            ),
            angularaxis=dict(
                gridcolor=COLORS["grid"],
                linecolor=COLORS["grid"],
                tickfont=dict(color=COLORS["text"], size=11),
            ),
        ),
        height=520,
    )
    return fig


# ── Barres comparatives ───────────────────────────────────────────────────────

def make_bar_comparison(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: str | None = None,
    title: str = "",
    orientation: str = "h",
    colors: list[str] | None = None,
) -> go.Figure:
    """Bar chart horizontal ou vertical avec colorisation par groupe."""
    if colors is None:
        colors = TEAM_COLORS

    fig = px.bar(
        df, x=x_col, y=y_col,
        color=color_col,
        orientation=orientation,
        color_discrete_sequence=colors,
        title=title,
    )
    fig.update_layout(**_base_layout())
    fig.update_traces(marker_line_width=0)
    return fig


def make_performance_index_bars(
    index_df: pd.DataFrame,
    title: str = "Indices de performance",
) -> go.Figure:
    """
    Bar chart groupé pour les indices composites.
    index_df : DataFrame [team, index, score].
    """
    teams = index_df["team"].unique().tolist()
    indices = index_df["index"].unique().tolist()
    colors = TEAM_COLORS

    fig = go.Figure()
    for i, team in enumerate(teams):
        sub = index_df[index_df["team"] == team]
        color = colors[i % len(colors)]
        fig.add_trace(go.Bar(
            x=sub["index"],
            y=sub["score"],
            name=team,
            marker_color=color,
            hovertemplate="%{x}: %{y:.1f}<extra>" + team + "</extra>",
        ))

    fig.update_layout(
        **_base_layout(
            title=dict(text=title, font=dict(size=16)),
            barmode="group",
            yaxis=dict(
                title="Score (percentile)",
                range=[0, 100],
                gridcolor=COLORS["grid"],
            ),
            xaxis=dict(tickangle=-20),
            height=420,
        )
    )
    return fig


# ── Scatter ───────────────────────────────────────────────────────────────────

def make_scatter(
    df: pd.DataFrame,
    x: str,
    y: str,
    text: str | None = None,
    size: str | None = None,
    color: str | None = None,
    title: str = "",
    xlab: str | None = None,
    ylab: str | None = None,
    highlight: list[str] | None = None,
) -> go.Figure:
    """
    Scatter plot avec annotations optionnelles (highlight = liste d'équipes à étiqueter).
    """
    fig = go.Figure()

    marker_color = df[color].map(lambda v: TEAM_COLORS[0]) if color else COLORS["accent_blue"]
    marker_size = (
        10 + 20 * (df[size] - df[size].min()) / (df[size].max() - df[size].min() + 1e-9)
        if size else 10
    )

    fig.add_trace(go.Scatter(
        x=df[x], y=df[y],
        mode="markers+text" if text and highlight else "markers",
        text=df[text] if text else None,
        textposition="top center",
        textfont=dict(color=COLORS["text"], size=10),
        marker=dict(
            size=marker_size,
            color=COLORS["accent_blue"],
            opacity=0.8,
            line=dict(color=COLORS["border"], width=1),
        ),
        hovertemplate=(
            f"<b>%{{text}}</b><br>{xlab or x}: %{{x:.2f}}<br>{ylab or y}: %{{y:.2f}}<extra></extra>"
            if text else f"{xlab or x}: %{{x:.2f}}<br>{ylab or y}: %{{y:.2f}}<extra></extra>"
        ),
    ))

    # Lignes de moyenne
    mx, my = df[x].mean(), df[y].mean()
    for val, axis in [(mx, "v"), (my, "h")]:
        fig.add_shape(
            type="line",
            **({
                "x0": val, "x1": val, "y0": df[y].min(), "y1": df[y].max()
            } if axis == "v" else {
                "x0": df[x].min(), "x1": df[x].max(), "y0": val, "y1": val
            }),
            line=dict(color=COLORS["text_muted"], width=1, dash="dot"),
        )

    fig.update_layout(
        **_base_layout(
            title=dict(text=title, font=dict(size=16)),
            xaxis=dict(title=xlab or x, gridcolor=COLORS["grid"]),
            yaxis=dict(title=ylab or y, gridcolor=COLORS["grid"]),
            height=480,
        )
    )
    return fig


# ── Ligne d'évolution ─────────────────────────────────────────────────────────

def make_line(
    df: pd.DataFrame,
    x: str,
    y_cols: list[str],
    labels: dict[str, str] | None = None,
    title: str = "",
    smooth: bool = False,
) -> go.Figure:
    """Line chart multi-series pour l'évolution temporelle."""
    fig = go.Figure()
    mode = "lines+markers"

    for i, col in enumerate(y_cols):
        color = TEAM_COLORS[i % len(TEAM_COLORS)]
        fig.add_trace(go.Scatter(
            x=df[x],
            y=df[col],
            name=labels.get(col, col) if labels else col,
            mode=mode,
            line=dict(color=color, width=2, shape="spline" if smooth else "linear"),
            marker=dict(size=5, color=color),
        ))

    fig.update_layout(
        **_base_layout(
            title=dict(text=title, font=dict(size=16)),
            xaxis=dict(gridcolor=COLORS["grid"]),
            yaxis=dict(gridcolor=COLORS["grid"]),
            height=380,
        )
    )
    return fig


# ── Distribution / percentile ─────────────────────────────────────────────────

def make_percentile_bars(
    metrics: dict[str, float],
    title: str = "",
    color: str | None = None,
) -> go.Figure:
    """
    Barres horizontales de percentile pour un joueur/équipe.
    metrics : {label: percentile 0-100}
    """
    color = color or COLORS["accent_green"]
    labels = list(metrics.keys())
    values = list(metrics.values())

    bar_colors = [
        COLORS["accent_red"] if v < 25 else
        COLORS["accent_gold"] if v < 50 else
        COLORS["accent_green"]
        for v in values
    ]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{v:.0f}" for v in values],
        textposition="outside",
        textfont=dict(color=COLORS["text"]),
        hovertemplate="%{y}: %{x:.1f}e percentile<extra></extra>",
    ))

    fig.update_layout(
        **_base_layout(
            title=dict(text=title, font=dict(size=16)),
            xaxis=dict(range=[0, 105], title="Percentile", gridcolor=COLORS["grid"]),
            yaxis=dict(autorange="reversed"),
            height=max(300, len(metrics) * 35),
        )
    )
    return fig


# ── PCA / Clustering ──────────────────────────────────────────────────────────

def make_pca_scatter(
    df: pd.DataFrame,
    x: str,
    y: str,
    cluster_col: str,
    label_col: str,
    cluster_names: dict[int, str] | None = None,
    title: str = "Clustering des styles de jeu",
    highlight: list[str] | None = None,
) -> go.Figure:
    """Scatter PCA avec coloration par cluster et annotation des équipes."""
    fig = go.Figure()
    clusters = sorted(df[cluster_col].unique())

    for i, c in enumerate(clusters):
        sub = df[df[cluster_col] == c]
        name = cluster_names.get(c, f"Cluster {c}") if cluster_names else f"Cluster {c}"
        color = TEAM_COLORS[i % len(TEAM_COLORS)]

        show_labels = highlight if highlight else sub[label_col].tolist()
        texts = sub[label_col].apply(lambda n: n if n in show_labels else "")

        fig.add_trace(go.Scatter(
            x=sub[x], y=sub[y],
            mode="markers+text",
            name=name,
            text=texts,
            textposition="top center",
            textfont=dict(color=COLORS["text"], size=9),
            marker=dict(
                size=10,
                color=color,
                opacity=0.85,
                line=dict(color=COLORS["border"], width=1),
            ),
            hovertemplate="<b>%{text}</b><br>PC1: %{x:.2f}<br>PC2: %{y:.2f}<extra>" + name + "</extra>",
        ))

    fig.update_layout(
        **_base_layout(
            title=dict(text=title, font=dict(size=16)),
            xaxis=dict(title="PC1", gridcolor=COLORS["grid"], zeroline=False),
            yaxis=dict(title="PC2", gridcolor=COLORS["grid"], zeroline=False),
            height=520,
        )
    )
    return fig


# ── Form strip ────────────────────────────────────────────────────────────────

# ── Radar MULTI-RÉFÉRENCE (focus + médiane + top10 + bottom10) ────────────────

def make_multi_radar(
    radar_data: dict,
    focus_name: str,
    title: str = "",
) -> go.Figure:
    """
    Radar avec 4 séries contextuelles type Football Insights :
      - Pire 10% (gris discret, fond)
      - Médiane ligue (jaune)
      - Top 10% (bleu)
      - Focus (vert, rempli)

    radar_data : dict issu de build_radar_with_context()
      {labels, focus, median, top10, bottom10}
    """
    labels = radar_data["labels"]
    if not labels:
        return go.Figure()

    cats = labels + [labels[0]]

    def _close(vals: list[float]) -> list[float]:
        return list(vals) + [vals[0]]

    fig = go.Figure()

    # Pire 10% (plus petit, fond discret)
    fig.add_trace(go.Scatterpolar(
        r=_close(radar_data["bottom10"]),
        theta=cats,
        mode="lines",
        line=dict(color=COLORS["text_muted"], width=1, dash="dot"),
        name="Pire 10%",
        hovertemplate="%{theta}: %{r:.2f}<extra>Pire 10%</extra>",
    ))

    # Médiane ligue (jaune)
    fig.add_trace(go.Scatterpolar(
        r=_close(radar_data["median"]),
        theta=cats,
        mode="lines",
        line=dict(color=COLORS["accent_gold"], width=2),
        name="Médiane ligue",
        hovertemplate="%{theta}: %{r:.2f}<extra>Médiane</extra>",
    ))

    # Top 10% (bleu)
    fig.add_trace(go.Scatterpolar(
        r=_close(radar_data["top10"]),
        theta=cats,
        mode="lines",
        line=dict(color=COLORS["accent_blue"], width=2),
        name="Top 10%",
        hovertemplate="%{theta}: %{r:.2f}<extra>Top 10%</extra>",
    ))

    # Focus (vert, rempli) — en dernier pour être au-dessus
    fig.add_trace(go.Scatterpolar(
        r=_close(radar_data["focus"]),
        theta=cats,
        fill="toself",
        fillcolor=_rgba(COLORS["accent_green"], 0.30),
        line=dict(color=COLORS["accent_green"], width=3),
        name=focus_name,
        hovertemplate="%{theta}: %{r:.2f}<extra>" + focus_name + "</extra>",
    ))

    fig.update_layout(**_base_layout(
        title=dict(text=title, font=dict(size=16)),
        polar=dict(
            bgcolor=COLORS["surface"],
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                showticklabels=False,
                gridcolor=COLORS["grid"],
                linecolor=COLORS["grid"],
            ),
            angularaxis=dict(
                gridcolor=COLORS["grid"],
                linecolor=COLORS["grid"],
                tickfont=dict(color=COLORS["text"], size=11),
            ),
        ),
        height=540,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.1,
            xanchor="center", x=0.5,
            bgcolor="rgba(0,0,0,0)",
            bordercolor=COLORS["border"],
            font=dict(color=COLORS["text"], size=11),
        ),
    ))
    return fig


# ── Percentile bars avec labels "Top X%" / "Pire X%" style FI ────────────────

def make_labeled_percentile_bars(
    rows: list[dict],
    title: str = "",
    max_items: int = 15,
) -> go.Figure:
    """
    Barres horizontales percentile style Football Insights.
    rows : [{metric, value, percentile, tag, tier}, ...] issu de build_percentiles_labeled()
    """
    if not rows:
        return go.Figure()

    rows = rows[:max_items]
    labels = [r["metric"] for r in rows]
    percentiles = [r["percentile"] for r in rows]
    values = [r["value"] for r in rows]
    tags = [r["tag"] for r in rows]

    # Couleur par tier : vert si top, rouge si bottom, gradient au milieu
    def _color(pct: float) -> str:
        if pct >= 75:  return COLORS["accent_green"]
        if pct >= 50:  return "#7ed957"
        if pct >= 25:  return COLORS["accent_gold"]
        return COLORS["accent_red"]

    colors = [_color(p) for p in percentiles]
    annotations_text = [
        f"<span style='color:{COLORS['text']}'>{v:.2f}</span> "
        f"<span style='color:{COLORS['text_muted']}'>· {t}</span>"
        for v, t in zip(values, tags)
    ]

    fig = go.Figure(go.Bar(
        x=percentiles,
        y=labels,
        orientation="h",
        marker_color=colors,
        marker_line_width=0,
        text=annotations_text,
        textposition="outside",
        hovertemplate="%{y}<br>Valeur : %{customdata[0]:.2f}<br>Percentile : %{x:.1f}<extra>%{customdata[1]}</extra>",
        customdata=list(zip(values, tags)),
    ))

    # Ligne verticale à 50 (médiane)
    fig.add_shape(
        type="line",
        x0=50, x1=50, y0=-0.5, y1=len(labels) - 0.5,
        line=dict(color=COLORS["text_muted"], width=1, dash="dash"),
    )
    fig.add_annotation(
        x=50, y=len(labels) - 0.3, text="Médiane",
        showarrow=False, font=dict(color=COLORS["text_muted"], size=10),
        xshift=-2, xanchor="right",
    )

    fig.update_layout(
        **_base_layout(
            title=dict(text=title, font=dict(size=16)),
            xaxis=dict(
                range=[0, 130],
                title="Percentile (0 = pire, 100 = meilleur)",
                gridcolor=COLORS["grid"],
                zeroline=False,
            ),
            yaxis=dict(autorange="reversed", tickfont=dict(size=12)),
            height=max(320, len(labels) * 38),
            margin=dict(l=20, r=120, t=50, b=40),
            showlegend=False,
        )
    )
    return fig


# ── Scatter de positionnement peer (2 axes percentile) ────────────────────────

def make_peer_scatter(
    df: pd.DataFrame,
    x_col: str, y_col: str,
    label_col: str,
    highlight: str | list[str] | None = None,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    annotate_top_n: int = 5,
) -> go.Figure:
    """
    Scatter 'peer positioning' : place une entité dans la distribution de ses pairs.
    Les axes sont généralement des percentiles 0-100.
    """
    if isinstance(highlight, str):
        highlight = [highlight] if highlight else []
    highlight = highlight or []

    # Couleur : vert si highlight, bleu sinon
    colors = [
        COLORS["accent_green"] if n in highlight else _rgba(COLORS["accent_blue"], 0.55)
        for n in df[label_col]
    ]
    sizes = [14 if n in highlight else 8 for n in df[label_col]]
    texts = [n if n in highlight else "" for n in df[label_col]]

    # Ajoute les top N si pas de highlight explicite
    if not highlight and annotate_top_n > 0:
        top = df.assign(dist=lambda d: (d[x_col] - 50).abs() + (d[y_col] - 50).abs()).nlargest(annotate_top_n, "dist")
        texts = [n if n in top[label_col].values else "" for n in df[label_col]]

    fig = go.Figure(go.Scatter(
        x=df[x_col], y=df[y_col],
        mode="markers+text",
        text=texts,
        textposition="top center",
        textfont=dict(color=COLORS["text"], size=10),
        marker=dict(
            color=colors,
            size=sizes,
            line=dict(color=COLORS["border"], width=0.5),
        ),
        customdata=df[label_col],
        hovertemplate=f"<b>%{{customdata}}</b><br>{x_label or x_col}: %{{x:.1f}}<br>{y_label or y_col}: %{{y:.1f}}<extra></extra>",
    ))

    # Quadrants
    fig.add_shape(type="line", x0=50, x1=50, y0=0, y1=100,
                  line=dict(color=COLORS["text_muted"], width=1, dash="dot"))
    fig.add_shape(type="line", x0=0, x1=100, y0=50, y1=50,
                  line=dict(color=COLORS["text_muted"], width=1, dash="dot"))

    fig.update_layout(
        **_base_layout(
            title=dict(text=title, font=dict(size=16)),
            xaxis=dict(range=[0, 105], title=x_label or x_col, gridcolor=COLORS["grid"]),
            yaxis=dict(range=[0, 105], title=y_label or y_col, gridcolor=COLORS["grid"]),
            height=480,
            showlegend=False,
        )
    )
    return fig


# ── Gauge (pour les KPIs indice composite) ────────────────────────────────────

def make_gauge(value: float, title: str, max_val: float = 100) -> go.Figure:
    """Jauge circulaire pour afficher un indice composite."""
    def _color(v: float) -> str:
        if v >= 75: return COLORS["accent_green"]
        if v >= 50: return "#7ed957"
        if v >= 25: return COLORS["accent_gold"]
        return COLORS["accent_red"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"color": COLORS["text"], "size": 14}},
        number={"font": {"color": COLORS["text"], "size": 32}},
        gauge={
            "axis": {"range": [0, max_val], "tickcolor": COLORS["text_muted"]},
            "bar": {"color": _color(value)},
            "bgcolor": COLORS["surface"],
            "borderwidth": 1,
            "bordercolor": COLORS["border"],
            "steps": [
                {"range": [0, 25], "color": _rgba(COLORS["accent_red"], 0.15)},
                {"range": [25, 50], "color": _rgba(COLORS["accent_gold"], 0.15)},
                {"range": [50, 75], "color": _rgba("#7ed957", 0.15)},
                {"range": [75, 100], "color": _rgba(COLORS["accent_green"], 0.15)},
            ],
        },
    ))
    fig.update_layout(**_base_layout(height=220, margin=dict(l=20, r=20, t=40, b=20)))
    return fig


RESULT_COLORS = {"W": "#00ff99", "D": "#ffd700", "L": "#ff4655"}
RESULT_LABELS = {"W": "V", "D": "N", "L": "D"}


def make_form_strip(results: list[str], team: str = "") -> go.Figure:
    """Mini bar chart coloré représentant la forme récente."""
    n = len(results)
    if n == 0:
        return go.Figure()

    fig = go.Figure()
    for i, r in enumerate(results[::-1]):  # plus récent à droite
        color = RESULT_COLORS.get(r, COLORS["text_muted"])
        fig.add_shape(
            type="rect",
            x0=i, x1=i + 0.85,
            y0=0, y1=1,
            fillcolor=color,
            opacity=0.85,
            line_width=0,
        )
        fig.add_annotation(
            x=i + 0.42, y=0.5,
            text=RESULT_LABELS.get(r, r),
            showarrow=False,
            font=dict(color=COLORS["bg"], size=14, family="Arial Black"),
        )

    fig.update_layout(
        **_base_layout(
            title=dict(text=f"Forme récente — {team}", font=dict(size=14)),
            xaxis=dict(visible=False, range=[-0.1, n + 0.1], fixedrange=True),
            yaxis=dict(visible=False, range=[0, 1], fixedrange=True),
            height=90,
            margin=dict(l=0, r=0, t=35, b=0),
            plot_bgcolor=COLORS["bg"],
        )
    )
    return fig


# ── Radar wedge (style DataScout : chaque axe = part de tarte colorée) ───────

def make_wedge_radar(
    labels: list[str],
    percentiles: list[float],
    title: str = "",
    size: int = 380,
) -> go.Figure:
    """
    Radar "wedge" : chaque axe devient une part de pizza colorée par quintile.
    Lecture sans légende possible (rouge=faible, vert=élite).
    """
    def _quintile_color(p: float) -> str:
        if p < 20:  return "#e85a4f"
        if p < 40:  return "#f0a04b"
        if p < 60:  return "#f5d76e"
        if p < 80:  return "#8ac765"
        return "#4dd887"

    if not labels:
        return go.Figure()

    colors = [_quintile_color(p) for p in percentiles]
    fig = go.Figure(go.Barpolar(
        r=percentiles,
        theta=labels,
        marker=dict(color=colors, line=dict(width=1.5, color="#16213e")),
        opacity=0.92,
        hovertemplate="<b>%{theta}</b><br>Percentile : %{r:.0f}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=title,
        height=size,
        showlegend=False,
        polar=dict(
            bgcolor="rgba(26,26,46,0.3)",
            radialaxis=dict(
                range=[0, 100],
                showticklabels=False,
                gridcolor="#2d2d4e",
                tickvals=[20, 40, 60, 80, 100],
            ),
            angularaxis=dict(
                gridcolor="#2d2d4e",
                tickfont=dict(size=10, color="#a0a3b1"),
            ),
        ),
    )
    return fig
