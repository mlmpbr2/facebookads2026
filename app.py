# -*- coding: utf-8 -*-
"""
app_dashboard_v3.py — Dashboard Eleições 2026 | Biblioteca de Anúncios da Meta
Execute:  streamlit run app_dashboard_v3.py
Entradas (nesta ordem de preferência):
  1) dados_meta_ads_enriquecido.csv   (saída do enriquecer_partidos_tse.py — recomendado)
  2) dados_meta_ads_final.csv + anunciantes_enriquecidos_tse.csv (o app faz o merge)
  3) dados_meta_ads_final.csv sozinho (sem partidos TSE)
"""
import os
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Eleições 2026 — Meta Ads", layout="wide", page_icon="📊")

# ---------------------------------------------------------------------------
# FORMATAÇÃO BR (compacta — nunca estoura a tela)
# ---------------------------------------------------------------------------
def fmt_rs(v):
    v = float(v)
    if abs(v) >= 1e9:
        return f"R$ {v/1e9:,.2f} bi".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs(v) >= 1e6:
        return f"R$ {v/1e6:,.1f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs(v) >= 1e3:
        return f"R$ {v/1e3:,.1f} mil".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {v:,.0f}".replace(",", ".")

def fmt_num(v):
    v = float(v)
    if abs(v) >= 1e6:
        return f"{v/1e6:,.1f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs(v) >= 1e3:
        return f"{v/1e3:,.1f} mil".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{v:,.0f}".replace(",", ".")

# ---------------------------------------------------------------------------
# DADOS
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    # prioridade: arquivo filtrado ELEIÇÃO 2026 > enriquecido íntegro > final + merge
    if os.path.exists("dados_meta_ads_eleicoes2026.csv"):
        df = pd.read_csv("dados_meta_ads_eleicoes2026.csv", encoding="utf-8-sig",
                         low_memory=False)
        return df, "eleicoes2026"
    if os.path.exists("dados_meta_ads_enriquecido.csv"):
        return pd.read_csv("dados_meta_ads_enriquecido.csv", encoding="utf-8-sig",
                           low_memory=False), "enriquecido"
    df = pd.read_csv("dados_meta_ads_final.csv", encoding="utf-8-sig", low_memory=False)
    if os.path.exists("anunciantes_enriquecidos_tse.csv"):
        enr = pd.read_csv("anunciantes_enriquecidos_tse.csv", encoding="utf-8-sig",
                          low_memory=False, dtype=str)
        cols_enr = ["chave_pagina", "partido_final", "numero_candidato",
                    "federacao_tse", "coligacao_tse", "nome_urna_tse",
                    "nome_partido_tse", "origem_match"]
        enr = enr[[c for c in cols_enr if c in enr.columns]].drop_duplicates("chave_pagina")
        df["chave_pagina"] = df["Page ID"].astype(str) + "|" + df["Page name"].astype(str)
        df = df.merge(enr, on="chave_pagina", how="left")
    return df, "final"

df, fonte_dados = load_data()

# se a base carregada NÃO é a filtrada, garante o filtro eleitoral por padrão
if fonte_dados != "eleicoes2026" and "eleitoral_eleicao2026" in df.columns:
    so_eleicao = st.sidebar.checkbox(
        "Somente anúncios ELEIÇÃO 2026 (recomendado)", value=True,
        help="Desmarque para incluir anúncios institucionais/privados na análise")
    if so_eleicao:
        df = df[df["eleitoral_eleicao2026"].astype(str).isin(["True", "true", "1"])]

# colunas de trabalho: partido/cargo definitivos
if "partido_final" not in df.columns:
    df["partido_final"] = df.get("partido", "Não identificado")
if "cargo_eleitoral" in df.columns:
    df["cargo_final"] = df["cargo_eleitoral"].fillna(df.get("cargo", "Não identificado"))
else:
    df["cargo_final"] = df.get("cargo", "Não identificado")
df["partido_final"] = df["partido_final"].fillna("Não identificado")
df["cargo_final"] = df["cargo_final"].fillna("Não identificado")

st.title("📊 Anúncios Políticos — Eleições 2026 (Biblioteca de Anúncios da Meta)")
st.markdown("Últimos 90 dias · granularidade **Página × Disclaimer × Estado** · "
            "partidos e números cruzados com o cadastro oficial de candidaturas do TSE.")

with st.expander("📖 Glossário e metodologia (clique para expandir)"):
    st.markdown("""
    - **Gasto de até R$ 100:** a Meta não informa o valor exato de gastos pequenos.
      Por isso mostramos sempre uma **faixa** (mínimo–máximo) e um valor **calibrado**
      que bate exatamente com os totais oficiais da Meta por estado.
    - **Partido e número:** obtidos do cadastro oficial do TSE (candidaturas 2026),
      cruzado pelo nome civil e nome de urna presentes no aviso legal do anúncio.
      Cobertura de **99,5%** dos anúncios eleitorais.
    - **Federação/Coligação:** quando o candidato disputa em bloco, o partido mostrado
      é sempre o **partido real do candidato**; o bloco aparece em coluna própria.
    - **Anunciantes do Instagram** sem página de Facebook aparecem individualmente
      (a Meta os agrupa sob um mesmo código; aqui eles são separados pelo nome).
    """)

# ---------------------------------------------------------------------------
# FILTROS
# ---------------------------------------------------------------------------
st.sidebar.header("🔎 Filtros")

METRICAS = {
    "Gasto calibrado (igual ao oficial Meta)": "gasto_calibrado",
    "Gasto estimado (ponto médio)": "gasto_estimado",
    "Gasto mínimo (piso)": "gasto_min",
    "Gasto máximo (teto)": "gasto_max",
}
metrica_label = st.sidebar.radio("Métrica de gasto", list(METRICAS.keys()))
metrica = METRICAS[metrica_label]

estados = ["Todos"] + sorted(df["Estado"].dropna().unique().tolist())
estado_sel = st.sidebar.selectbox(
    "Estado de veiculação (Meta)", estados,
    help="Onde o anúncio foi EXIBIDO segundo a Meta — não é o estado do candidato")

# UF de registro do candidato (vem do cruzamento TSE)
if "uf_tse" in df.columns:
    ufs_cand = ["Todas"] + sorted(df["uf_tse"].dropna().unique().tolist())
    uf_cand_sel = st.sidebar.selectbox(
        "UF do candidato (TSE)", ufs_cand,
        help="Estado onde o candidato está registrado no TSE — use aqui para ver "
             "senadores/deputados DE um estado")
else:
    uf_cand_sel = "Todas"

cargos = ["Todos"] + sorted(df["cargo_final"].dropna().unique().tolist())
cargo_sel = st.sidebar.selectbox("Cargo", cargos)

partidos = ["Todos"] + sorted(df["partido_final"].dropna().unique().tolist())
partido_sel = st.sidebar.selectbox("Partido", partidos)

busca = st.sidebar.text_input("Buscar candidato/página")

f = df.copy()
if estado_sel != "Todos":
    f = f[f["Estado"] == estado_sel]
if uf_cand_sel != "Todas":
    f = f[f["uf_tse"] == uf_cand_sel]
if cargo_sel != "Todos":
    f = f[f["cargo_final"] == cargo_sel]
if partido_sel != "Todos":
    f = f[f["partido_final"] == partido_sel]
if busca.strip():
    f = f[f["Page name"].str.contains(busca.strip(), case=False, na=False)]

if f.empty:
    st.warning("Nenhum registro com os filtros selecionados.")
    st.stop()

# ---------------------------------------------------------------------------
# ABAS
# ---------------------------------------------------------------------------
tab1, tab2 = st.tabs(["📈 Visão Geral", "⚖️ Comparar Candidatos"])

# ===========================================================================
# ABA 1 — VISÃO GERAL
# ===========================================================================
def fmt_int(v):
    """Número exato com separador de milhar BR: 266366000 -> 266.366.000"""
    return f"{int(round(float(v))):,}".replace(",", ".")

def kpi_card(titulo, valor, detalhe=""):
    return (f"<div style='background:#262730;border-radius:10px;padding:12px 14px;"
            f"min-height:118px;border:1px solid #3a3d4d'>"
            f"<div style='color:#a3a8b8;font-size:0.82rem;margin-bottom:4px'>{titulo}</div>"
            f"<div style='color:#fafafa;font-size:1.45rem;font-weight:650;"
            f"line-height:1.2;word-break:break-word'>{valor}</div>"
            f"<div style='color:#7d8090;font-size:0.72rem;margin-top:6px'>{detalhe}</div>"
            f"</div>")

with tab1:
    g_min, g_max = f["gasto_min"].sum(), f["gasto_max"].sum()
    g_cal = f["gasto_calibrado"].sum()
    n_pag = f["chave_pagina"].nunique()
    n_ads = (f.drop_duplicates("chave_pagina")
               .pipe(lambda d: pd.to_numeric(d["ads_na_biblioteca"], errors="coerce"))
               .fillna(0).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card(
        "Investimento (faixa min–máx)",
        f"{fmt_rs(g_min)} – {fmt_rs(g_max)}",
        f"Exato: R$ {fmt_int(g_min)} – R$ {fmt_int(g_max)}"), unsafe_allow_html=True)
    c2.markdown(kpi_card(
        "Gasto calibrado", fmt_rs(g_cal),
        f"Exato: R$ {fmt_int(g_cal)}"), unsafe_allow_html=True)
    c3.markdown(kpi_card(
        "Candidatos/páginas únicas", fmt_num(n_pag),
        f"Exato: {fmt_int(n_pag)}"), unsafe_allow_html=True)
    c4.markdown(kpi_card(
        "Anúncios na biblioteca", fmt_num(n_ads),
        f"Exato: {fmt_int(n_ads)}"), unsafe_allow_html=True)

    pct_cens = f["gasto_censurado"].mean() * 100
    st.caption(f"{len(f):,} registros analisados · {pct_cens:.0f}% com gasto de até "
               f"R$ 100 (valor exato não divulgado pela Meta) · "
               f"partido identificado via TSE em 99,5% dos anúncios eleitorais"
               .replace(",", "."))
    st.markdown("---")

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Investimento por Estado")
        g = (f.groupby("Estado", as_index=False)[metrica].sum()
               .sort_values(metrica, ascending=True))
        fig = px.bar(g, x=metrica, y="Estado", orientation="h",
                     labels={metrica: "R$", "Estado": ""},
                     color=metrica, color_continuous_scale="Blues")
        fig.update_layout(height=520, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Top 15 Candidatos/Campanhas")
        g = (f.groupby(["Page name", "partido_final"], as_index=False)[metrica].sum()
               .sort_values(metrica, ascending=False).head(15))
        fig = px.bar(g, x=metrica, y="Page name", orientation="h",
                     color="partido_final",
                     labels={metrica: "R$", "Page name": "", "partido_final": "Partido"})
        fig.update_layout(height=520, yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("Investimento por Cargo")
        g = (f.groupby("cargo_final", as_index=False)[metrica].sum()
               .sort_values(metrica, ascending=False))
        fig = px.pie(g, names="cargo_final", values=metrica, hole=0.45)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(height=450, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_d:
        st.subheader("Investimento por Partido")
        g = (f[f["partido_final"] != "Não identificado"]
               .groupby("partido_final", as_index=False)[metrica].sum()
               .sort_values(metrica, ascending=False).head(15))
        if g.empty:
            st.info("Nenhum partido identificado com os filtros atuais.")
        else:
            fig = px.bar(g, x="partido_final", y=metrica, color=metrica,
                         color_continuous_scale="Teal",
                         labels={metrica: "R$", "partido_final": "Partido"})
            fig.update_layout(height=450, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

    # --- Eficiência em linguagem simples: custo por anúncio ---
    st.subheader("💡 Quanto custa cada anúncio? (Top 20 campanhas por investimento)")
    st.caption("Leitura simples: barras maiores = cada anúncio individual custou mais caro. "
               "Barras menores = campanha pulverizada em muitos anúncios baratos.")
    g = (f.groupby(["Page name", "partido_final"], as_index=False)
           .agg(gasto=(metrica, "sum"),
                ads=("ads_na_biblioteca", lambda s: pd.to_numeric(s, errors="coerce").max())))
    g["ads"] = g["ads"].replace(0, pd.NA)
    g["custo_por_anuncio"] = g["gasto"] / g["ads"]
    g = g.dropna(subset=["custo_por_anuncio"]).sort_values("gasto", ascending=False).head(20)
    fig = px.bar(g.sort_values("custo_por_anuncio"),
                 x="custo_por_anuncio", y="Page name", orientation="h",
                 color="partido_final",
                 labels={"custo_por_anuncio": "Custo médio por anúncio (R$)",
                         "Page name": "", "partido_final": "Partido"})
    fig.update_layout(height=560)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 Tabela detalhada")
    cols_show = [c for c in ["Page name", "nome_urna_tse", "numero_candidato",
                             "partido_final", "federacao_tse", "cargo_final",
                             "uf_tse", "Estado", "gasto_bruto", "gasto_calibrado",
                             "ads_na_biblioteca"] if c in f.columns]
    st.dataframe(f[cols_show].sort_values("gasto_calibrado", ascending=False).head(500),
                 use_container_width=True, height=420)
    st.download_button("⬇️ Baixar recorte filtrado (CSV)",
                       f[cols_show].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                       "recorte_meta_ads.csv", "text/csv")

# ===========================================================================
# ABA 2 — COMPARAR CANDIDATOS
# ===========================================================================
with tab2:
    st.subheader("Compare candidatos lado a lado")
    opcoes = (f.groupby("Page name")[metrica].sum()
                .sort_values(ascending=False).index.tolist())
    selecionados = st.multiselect(
        "Escolha de 2 a 6 candidatos/campanhas (ordenados por investimento)",
        opcoes, default=opcoes[:2] if len(opcoes) >= 2 else opcoes)

    if len(selecionados) < 2:
        st.info("Selecione pelo menos 2 candidatos para comparar.")
    else:
        comp = f[f["Page name"].isin(selecionados[:6])]
        resumo = (comp.groupby("Page name", as_index=False)
                    .agg(partido=("partido_final", "first"),
                         numero=("numero_candidato", "first") if "numero_candidato" in comp else ("partido_final", "first"),
                         investimento_min=("gasto_min", "sum"),
                         investimento_max=("gasto_max", "sum"),
                         investimento_calibrado=("gasto_calibrado", "sum"),
                         anuncios=("ads_na_biblioteca", lambda s: pd.to_numeric(s, errors="coerce").max()),
                         estados_presentes=("Estado", "nunique")))
        resumo["custo_por_anuncio"] = resumo["investimento_calibrado"] / resumo["anuncios"].replace(0, pd.NA)

        # cartões lado a lado
        cols = st.columns(len(resumo))
        for col, (_, r) in zip(cols, resumo.iterrows()):
            with col:
                st.markdown(f"**{r['Page name']}**")
                st.caption(f"{r['partido']}" +
                           (f" · Nº {r['numero']}" if pd.notna(r['numero']) else ""))
                st.metric("Investimento", fmt_rs(r["investimento_calibrado"]),
                          help=f"Faixa: {fmt_rs(r['investimento_min'])} – {fmt_rs(r['investimento_max'])}")
                st.metric("Anúncios", fmt_num(r["anuncios"]))
                st.metric("Estados", int(r["estados_presentes"]))

        st.markdown("---")
        cc1, cc2 = st.columns(2)
        with cc1:
            fig = px.bar(resumo, x="Page name", y="investimento_calibrado",
                         color="partido", text=resumo["investimento_calibrado"].apply(fmt_rs),
                         title="Investimento total (calibrado)",
                         labels={"Page name": "", "investimento_calibrado": "R$",
                                 "partido": "Partido"})
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        with cc2:
            fig = px.bar(resumo, x="Page name", y="custo_por_anuncio",
                         color="partido",
                         text=resumo["custo_por_anuncio"].apply(fmt_rs),
                         title="Custo médio por anúncio",
                         labels={"Page name": "", "custo_por_anuncio": "R$",
                                 "partido": "Partido"})
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

        # distribuição geográfica comparada
        st.subheader("Onde cada um investe (por estado)")
        g = (comp.groupby(["Page name", "Estado"], as_index=False)[metrica].sum())
        fig = px.bar(g, x="Estado", y=metrica, color="Page name", barmode="group",
                     labels={metrica: "R$", "Page name": "Candidato"})
        fig.update_layout(height=460)
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# RODAPÉ
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:grey; font-size:0.85em'>"
    "Powered by Mario Mello, using Python, Pandas, Streamlit — Enhanced by Kimi k3 — high"
    "</p>", unsafe_allow_html=True)
