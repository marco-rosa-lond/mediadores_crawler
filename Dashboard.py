"""
Dashboard interativo — Plataforma de Análise de Mediadores de Seguros
======================================================================
Execução:
    streamlit run dashboard.py

Requisitos adicionais:
    pip install streamlit plotly pandas openpyxl
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import DB_PATH

# ── Configuração da página ────────────────────────────────────────────────────

st.set_page_config(
    page_title="Mediadores · Análise",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Paleta e estilos ──────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Sora:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Sora', sans-serif;
}

/* Fundo geral */
.stApp {
    background-color: #0b0f1a;
    color: #e2e8f0;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #111827;
    border-right: 1px solid #1e293b;
}

/* Métricas */
[data-testid="metric-container"] {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 16px 20px;
}
[data-testid="metric-container"] label {
    color: #64748b !important;
    font-size: 11px !important;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-family: 'DM Mono', monospace !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #f1f5f9 !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
    font-family: 'Sora', sans-serif !important;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-family: 'DM Mono', monospace !important;
    font-size: 12px !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #111827;
    border-radius: 10px;
    padding: 4px;
    gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #64748b;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    padding: 8px 18px;
}
.stTabs [aria-selected="true"] {
    background: #1e293b !important;
    color: #38bdf8 !important;
}

/* Tabela de dados */
.stDataFrame {
    background: #111827;
    border-radius: 10px;
}

/* Cabeçalho da secção */
.section-header {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #38bdf8;
    margin-bottom: 4px;
    margin-top: 24px;
}
.big-title {
    font-size: 2.2rem;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: -0.02em;
    line-height: 1.1;
}
.subtitle {
    color: #64748b;
    font-size: 14px;
    margin-top: 4px;
}

/* Scorecard de mediador */
.mediador-card {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 12px;
    transition: border-color 0.2s;
}
.mediador-card:hover { border-color: #38bdf8; }

/* Badge */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-family: 'DM Mono', monospace;
    font-weight: 500;
    margin-right: 4px;
}
.badge-sim  { background: #0c4a6e; color: #38bdf8; }
.badge-form { background: #134e4a; color: #2dd4bf; }
.badge-part { background: #3b1764; color: #c084fc; }
.badge-err  { background: #450a0a; color: #f87171; }

/* Progress bar customizada */
.score-bar-wrap { margin: 4px 0 12px; }
.score-label { font-size: 12px; color: #94a3b8; margin-bottom: 3px; font-family: 'DM Mono', monospace; }

/* Divider subtil */
hr { border-color: #1e293b !important; }

/* Inputs sidebar */
.stSelectbox label, .stMultiSelect label, .stSlider label, .stCheckbox label {
    color: #94a3b8 !important;
    font-size: 12px !important;
}

/* Plot backgrounds */
.js-plotly-plot .plotly .bg { fill: transparent !important; }
</style>
""", unsafe_allow_html=True)


# ── Funções de dados ──────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_data(db_path: str = DB_PATH):
    """Carrega todos os dados da BD SQLite."""
    if not Path(db_path).exists():
        return None, None, None, None

    with sqlite3.connect(db_path) as conn:
        mediadores = pd.read_sql("SELECT * FROM mediadores", conn)
        pages = pd.read_sql("SELECT * FROM pages", conn)
        seguradoras = pd.read_sql("SELECT * FROM seguradoras_detetadas", conn)
        detections = pd.read_sql("SELECT * FROM detections", conn)

    # Tipos
    for col in ["has_simulator", "has_contact_form", "has_partners"]:
        if col in mediadores.columns:
            mediadores[col] = mediadores[col].astype(bool)

    return mediadores, pages, seguradoras, detections


def demo_data():
    """Dados de demonstração para quando não existe BD real."""
    import numpy as np
    rng = np.random.default_rng(42)

    n = 120
    urls = [f"https://mediador{i:03d}.pt" for i in range(n)]
    status = rng.choice(["ok", "ok", "ok", "error", "timeout"], n)
    has_sim = rng.random(n) > 0.55
    has_form = rng.random(n) > 0.40
    has_part = rng.random(n) > 0.35

    mediadores = pd.DataFrame({
        "id": range(1, n + 1),
        "base_url": urls,
        "nome": [None] * n,
        "has_simulator": has_sim,
        "simulator_score": rng.uniform(0, 1, n).round(2),
        "has_contact_form": has_form,
        "contact_form_score": rng.uniform(0, 1, n).round(2),
        "has_partners": has_part,
        "seguradoras_count": rng.integers(0, 9, n),
        "pages_crawled": rng.integers(1, 8, n),
        "status": status,
        "error_msg": [None] * n,
        "crawled_at": pd.date_range("2024-01-01", periods=n, freq="1h").astype(str),
    })

    segs_list = ["Fidelidade", "Allianz", "AXA", "Tranquilidade", "Generali",
                 "Zurich", "Ageas", "Lusitania", "Liberty", "Groupama",
                 "Multicare", "Médis", "Logo"]
    rows = []
    for mid in range(1, n + 1):
        chosen = rng.choice(segs_list, size=rng.integers(0, 6), replace=False)
        for seg in chosen:
            rows.append({"mediador_id": mid, "seguradora": seg,
                         "score": round(rng.uniform(0.3, 1.0), 2), "fonte": "texto"})
    seguradoras = pd.DataFrame(rows)

    pages = pd.DataFrame({
        "id": range(1, n * 3 + 1),
        "mediador_id": rng.integers(1, n + 1, n * 3),
        "url": [f"https://mediador{rng.integers(0,n):03d}.pt/page{j}" for j in range(n * 3)],
        "title": ["Página"] * (n * 3),
        "http_status": rng.choice([200, 200, 200, 301, 404], n * 3),
        "text_snippet": ["..."] * (n * 3),
        "crawled_at": [""] * (n * 3),
    })

    detections = pd.DataFrame(columns=["id", "mediador_id", "tipo", "score",
                                        "evidencias_json", "page_url"])
    return mediadores, pages, seguradoras, detections


# ── Layout principal ──────────────────────────────────────────────────────────

# Cabeçalho
st.markdown("""
<div style="padding: 8px 0 24px;">
  <div class="section-header">🛡️ plataforma de análise</div>
  <div class="big-title">Mediadores de Seguros</div>
  <div class="subtitle">Portugal · Monitorização e inteligência de mercado</div>
</div>
""", unsafe_allow_html=True)

# Carregar dados
mediadores, pages, seguradoras, detections = load_data()
is_demo = mediadores is None

if is_demo:
    st.info("ℹ️ **Modo demonstração** — Não foi encontrada a base de dados `mediadores.db`. "
            "Execute o pipeline primeiro ou veja aqui dados simulados.", icon="💡")
    mediadores, pages, seguradoras, detections = demo_data()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Filtros")

    status_filter = st.multiselect(
        "Estado do crawl",
        options=["ok", "error", "timeout"],
        default=["ok"],
    )

    sim_filter = st.checkbox("Só com simulador", value=False)
    form_filter = st.checkbox("Só com formulário de contacto", value=False)
    part_filter = st.checkbox("Só com parceiros/seguradoras", value=False)

    all_segs = sorted(seguradoras["seguradora"].unique().tolist()) if len(seguradoras) else []
    seg_filter = st.multiselect("Seguradora detetada", options=all_segs, default=[])

    min_score = st.slider("Score mínimo simulador", 0.0, 1.0, 0.0, 0.05)

    st.markdown("---")
    if st.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown(
        "<div style='font-size:11px; color:#475569; font-family:DM Mono,monospace;'>"
        f"BD: {'demo' if is_demo else DB_PATH}<br>"
        f"Mediadores: {len(mediadores)}</div>",
        unsafe_allow_html=True,
    )

# Aplicar filtros
df = mediadores.copy()
if status_filter:
    df = df[df["status"].isin(status_filter)]
if sim_filter:
    df = df[df["has_simulator"] == True]
if form_filter:
    df = df[df["has_contact_form"] == True]
if part_filter:
    df = df[df["has_partners"] == True]
if min_score > 0:
    df = df[df["simulator_score"] >= min_score]
if seg_filter:
    ids_with_seg = seguradoras[seguradoras["seguradora"].isin(seg_filter)]["mediador_id"].unique()
    df = df[df["id"].isin(ids_with_seg)]

# ── KPIs ──────────────────────────────────────────────────────────────────────

total = len(df)
n_sim = int(df["has_simulator"].sum())
n_form = int(df["has_contact_form"].sum())
n_err = int((df["status"] != "ok").sum())
avg_segs = round(df["seguradoras_count"].mean(), 1) if total else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Sites analisados", total)
k2.metric("Com simulador", n_sim,
          delta=f"{n_sim/total*100:.0f}%" if total else None)
k3.metric("Com formulário contacto", n_form,
          delta=f"{n_form/total*100:.0f}%" if total else None)
k4.metric("Média seguradoras/site", avg_segs)
k5.metric("Erros / timeouts", n_err,
          delta=f"{'⚠' if n_err > total*0.1 else '✓'}",
          delta_color="inverse" if n_err > total * 0.1 else "normal")

st.markdown("<hr>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "📊  Visão geral",
    "🏢  Seguradoras",
    "🔍  Mediadores",
    "📋  Dados brutos",
])

PLOT_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Sora, sans-serif", color="#94a3b8", size=12),
    margin=dict(l=0, r=0, t=30, b=0),
)
GRID_STYLE = dict(gridcolor="#1e293b", zerolinecolor="#1e293b")


# ─── Tab 1: Visão geral ───────────────────────────────────────────────────────

with tab1:

    col_a, col_b = st.columns(2, gap="large")

    with col_a:
        st.markdown('<div class="section-header">Distribuição por tipo de site</div>',
                    unsafe_allow_html=True)

        sim_only = int(((df["has_simulator"]) & (~df["has_contact_form"])).sum())
        form_only = int(((~df["has_simulator"]) & df["has_contact_form"]).sum())
        both = int((df["has_simulator"] & df["has_contact_form"]).sum())
        neither    = total - sim_only - form_only - both

        fig_pie = go.Figure(go.Pie(
            labels=["Só simulador", "Só formulário", "Simulador + formulário", "Básico"],
            values=[sim_only, form_only, both, neither],
            hole=0.6,
            marker_colors=["#38bdf8", "#2dd4bf", "#818cf8", "#334155"],
            textfont=dict(family="DM Mono, monospace", size=11),
            textinfo="percent+label",
        ))
        fig_pie.update_layout(**PLOT_THEME, height=320,
                              legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        st.markdown('<div class="section-header">Score de simulador — distribuição</div>',
                    unsafe_allow_html=True)
        fig_hist = go.Figure(go.Histogram(
            x=df["simulator_score"],
            nbinsx=20,
            marker_color="#38bdf8",
            marker_line_color="#0369a1",
            marker_line_width=0.5,
        ))
        fig_hist.update_layout(**PLOT_THEME, height=320,
                               xaxis=dict(title="Score", **GRID_STYLE),
                               yaxis=dict(title="Nº sites", **GRID_STYLE))
        st.plotly_chart(fig_hist, use_container_width=True)

    st.markdown('<div class="section-header">Páginas visitadas por site</div>',
                unsafe_allow_html=True)

    pages_per_site = (
        pages[pages["mediador_id"].isin(df["id"])]
        .groupby("mediador_id")["url"].count()
        .reset_index(name="n_pages")
    )
    fig_pages = px.histogram(
        pages_per_site, x="n_pages", nbins=10,
        color_discrete_sequence=["#818cf8"],
        labels={"n_pages": "Páginas visitadas"},
    )
    fig_pages.update_layout(**PLOT_THEME, height=260,
                            xaxis={**GRID_STYLE},
                            yaxis={**GRID_STYLE, "title": "Nº mediadores"})
    st.plotly_chart(fig_pages, use_container_width=True)


# ─── Tab 2: Seguradoras ───────────────────────────────────────────────────────

with tab2:

    if len(seguradoras) == 0:
        st.warning("Sem dados de seguradoras.")
    else:
        segs_filtered = seguradoras[seguradoras["mediador_id"].isin(df["id"])]

        col_a, col_b = st.columns([3, 2], gap="large")

        with col_a:
            st.markdown('<div class="section-header">Seguradoras mais frequentes</div>',
                        unsafe_allow_html=True)

            top_segs = (
                segs_filtered.groupby("seguradora")["mediador_id"]
                .nunique()
                .sort_values(ascending=True)
                .tail(15)
                .reset_index(name="n_mediadores")
            )
            fig_bar = go.Figure(go.Bar(
                x=top_segs["n_mediadores"],
                y=top_segs["seguradora"],
                orientation="h",
                marker_color="#38bdf8",
                marker_line_width=0,
                text=top_segs["n_mediadores"],
                textposition="outside",
                textfont=dict(family="DM Mono, monospace", size=11, color="#94a3b8"),
            ))
            fig_bar.update_layout(
                **PLOT_THEME, height=420,
                xaxis=dict(title="Nº mediadores", **GRID_STYLE),
                yaxis=dict(tickfont=dict(family="DM Mono, monospace", size=11)),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_b:
            st.markdown('<div class="section-header">Score médio por seguradora</div>',
                        unsafe_allow_html=True)

            avg_score = (
                segs_filtered.groupby("seguradora")["score"]
                .mean()
                .sort_values(ascending=False)
                .round(2)
                .reset_index()
            )
            fig_score = go.Figure(go.Bar(
                x=avg_score["seguradora"],
                y=avg_score["score"],
                marker_color="#818cf8",
                marker_line_width=0,
            ))
            fig_score.update_layout(
                **PLOT_THEME, height=420,
                xaxis=dict(tickangle=-40, tickfont=dict(size=10)),
                yaxis=dict(title="Score médio", range=[0, 1], **GRID_STYLE),
            )
            st.plotly_chart(fig_score, use_container_width=True)

        # Heatmap mediador × seguradora (top 20 mediadores por n_segs)
        st.markdown('<div class="section-header">Mapa de cobertura (top 30 mediadores)</div>',
                    unsafe_allow_html=True)

        top_ids = (
            segs_filtered.groupby("mediador_id")["seguradora"].count()
            .nlargest(30).index
        )
        pivot = (
            segs_filtered[segs_filtered["mediador_id"].isin(top_ids)]
            .pivot_table(index="mediador_id", columns="seguradora",
                         values="score", aggfunc="max", fill_value=0)
        )
        # Label curto para eixo y
        id_to_url = df.set_index("id")["base_url"].str.replace(
            r"https?://(www\.)?", "", regex=True).str[:30]
        pivot.index = pivot.index.map(lambda i: id_to_url.get(i, str(i)))

        fig_heat = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[[0, "#0b0f1a"], [0.3, "#0c4a6e"], [1, "#38bdf8"]],
            showscale=True,
            colorbar=dict(thickness=10, len=0.6,
                          tickfont=dict(family="DM Mono, monospace", size=10)),
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:.2f}<extra></extra>",
        ))
        fig_heat.update_layout(
            **PLOT_THEME,
            height=max(380, len(pivot) * 18),
            xaxis=dict(tickangle=-35, tickfont=dict(size=10)),
            yaxis=dict(tickfont=dict(family="DM Mono, monospace", size=9)),
        )
        st.plotly_chart(fig_heat, use_container_width=True)


# ─── Tab 3: Mediadores (explorador) ──────────────────────────────────────────

with tab3:

    st.markdown('<div class="section-header">Explorador de mediadores</div>',
                unsafe_allow_html=True)

    search = st.text_input("🔎 Pesquisar URL", placeholder="ex: fidelidade, lisboa...")
    df_show = df.copy()
    if search:
        df_show = df_show[df_show["base_url"].str.contains(search, case=False, na=False)]

    sort_col = st.selectbox(
        "Ordenar por",
        ["simulator_score", "contact_form_score", "seguradoras_count", "pages_crawled"],
    )
    df_show = df_show.sort_values(sort_col, ascending=False)

    st.markdown(f"**{len(df_show)}** mediadores", unsafe_allow_html=False)

    # Cards por mediador
    for _, row in df_show.head(50).iterrows():
        badges = ""
        if row.get("has_simulator"):
            badges += '<span class="badge badge-sim">simulador</span>'
        if row.get("has_contact_form"):
            badges += '<span class="badge badge-form">formulário</span>'
        if row.get("has_partners"):
            badges += '<span class="badge badge-part">parceiros</span>'
        if row.get("status") != "ok":
            badges += f'<span class="badge badge-err">{row.get("status","?")}</span>'

        sim_pct = int(row.get("simulator_score", 0) * 100)
        form_pct = int(row.get("contact_form_score", 0) * 100)

        # Seguradoras deste mediador
        segs_here = seguradoras[seguradoras["mediador_id"] == row["id"]]["seguradora"].tolist()
        segs_str = " · ".join(segs_here[:8]) + (" …" if len(segs_here) > 8 else "") if segs_here else "—"

        st.markdown(f"""
        <div class="mediador-card">
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div>
              <div style="font-size:14px; font-weight:600; color:#f1f5f9; margin-bottom:4px;">
                {row['base_url']}
              </div>
              <div style="margin-bottom:10px;">{badges}</div>
            </div>
            <div style="text-align:right; font-family:'DM Mono',monospace; font-size:11px; color:#475569;">
              {row.get('pages_crawled', 0)} pág. · {row.get('seguradoras_count', 0)} seg.
            </div>
          </div>

          <div class="score-bar-wrap">
            <div class="score-label">Simulador &nbsp;<b style="color:#38bdf8">{sim_pct}%</b></div>
            <div style="background:#1e293b; border-radius:4px; height:5px;">
              <div style="background:#38bdf8; width:{sim_pct}%; height:5px; border-radius:4px;"></div>
            </div>
          </div>
          <div class="score-bar-wrap">
            <div class="score-label">Formulário &nbsp;<b style="color:#2dd4bf">{form_pct}%</b></div>
            <div style="background:#1e293b; border-radius:4px; height:5px;">
              <div style="background:#2dd4bf; width:{form_pct}%; height:5px; border-radius:4px;"></div>
            </div>
          </div>

          <div style="font-size:11px; color:#475569; font-family:'DM Mono',monospace; margin-top:6px;">
            Seguradoras: <span style="color:#94a3b8">{segs_str}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    if len(df_show) > 50:
        st.caption(f"A mostrar 50 de {len(df_show)}. Use os filtros para refinar.")


# ─── Tab 4: Dados brutos ──────────────────────────────────────────────────────

with tab4:

    st.markdown('<div class="section-header">Exportar dados</div>',
                unsafe_allow_html=True)

    col_dl1, col_dl2, col_dl3 = st.columns(3)

    with col_dl1:
        csv_med = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Mediadores CSV", csv_med,
                           "mediadores.csv", "text/csv",
                           use_container_width=True)
    with col_dl2:
        if len(seguradoras):
            csv_seg = seguradoras.to_csv(index=False).encode("utf-8")
            st.download_button("⬇ Seguradoras CSV", csv_seg,
                               "seguradoras.csv", "text/csv",
                               use_container_width=True)
    with col_dl3:
        if len(pages):
            csv_pag = pages.to_csv(index=False).encode("utf-8")
            st.download_button("⬇ Páginas CSV", csv_pag,
                               "pages.csv", "text/csv",
                               use_container_width=True)

    st.markdown('<div class="section-header">Tabela de mediadores</div>',
                unsafe_allow_html=True)

    display_cols = [
        "base_url", "status", "has_simulator", "simulator_score",
        "has_contact_form", "contact_form_score", "has_partners",
        "seguradoras_count", "pages_crawled", "crawled_at",
    ]
    st.dataframe(
        df[[c for c in display_cols if c in df.columns]],
        use_container_width=True,
        height=500,
        column_config={
            "base_url":           st.column_config.TextColumn("URL"),
            "simulator_score":    st.column_config.ProgressColumn("Score Sim.", min_value=0, max_value=1),
            "contact_form_score": st.column_config.ProgressColumn("Score Form.", min_value=0, max_value=1),
            "has_simulator":      st.column_config.CheckboxColumn("Simulador"),
            "has_contact_form":   st.column_config.CheckboxColumn("Formulário"),
            "has_partners":       st.column_config.CheckboxColumn("Parceiros"),
        },
        hide_index=True,
    )