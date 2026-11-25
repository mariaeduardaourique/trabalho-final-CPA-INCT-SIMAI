from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


# -----------------------------------------------------------------------------
# Configuração da página
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Municípios atingidos no RS",
    page_icon="🗺️",
    layout="wide",
)

ORDEM_SITUACAO = ["Calamidade", "Emergência", "Não Homologado"]

CORES_SITUACAO = {
    "Calamidade": "#C73E3A",
    "Emergência": "#F28E5B",
    "Não Homologado": "#87BCE8",
}

ESCALA_SITUACAO = alt.Scale(
    domain=list(CORES_SITUACAO.keys()),
    range=list(CORES_SITUACAO.values()),
)

METRICAS = {
    "Pessoas atingidas": "pop_atingida",
    "Domicílios atingidos": "domicilios_atingidos",
    "Endereços atingidos": "enderecos_atingidos",
    "Pessoas no CadÚnico atingidas": "cad_pessoas_atingidas",
    "CNPJs atingidos": "cnpjs_atingidos",
    "Equipamentos atingidos": "equipamentos_atingidos",
    "Km atingidos": "km_atingidos",
    "Auxílios VPC (quantidade)": "vpc_auxilios",
    "Auxílios SOS RS (quantidade)": "sosrs_auxilios",
    "Valor repassado (R$)": "valor_total_rs",
}

COLUNAS_TEXTO = [
    "codigo_ibge",
    "municipio",
    "situacao",
    "corede",
    "municipio_chave",
    "flag",
    "km_atingidos_era_vazio",
]

FLAG_REDUNDANTE = "não homologado com impacto registrado"


def formatar_numero(valor):
    """Formata inteiros no padrão brasileiro (1.234)."""
    return f"{int(round(valor)):,.0f}".replace(",", ".")


def formatar_moeda(valor):
    """Formata valores em reais de forma compacta (R$ 12,3 mi)."""
    if valor >= 1_000_000:
        return "R$ " + f"{valor / 1_000_000:.1f}".replace(".", ",") + " mi"
    return "R$ " + formatar_numero(valor)


def formatar_percentual(valor):
    """Formata uma fração (0 a 1) como percentual brasileiro (82,1%)."""
    return f"{valor * 100:.1f}".replace(".", ",") + "%"


# -----------------------------------------------------------------------------
# Carregamento e tratamento dos dados
# -----------------------------------------------------------------------------

@st.cache_data
def carregar_dados():
    raiz_projeto = Path(__file__).resolve().parent.parent
    caminho_arquivo = raiz_projeto / "dados" / "processados" / "muprs_limpo.csv"

    dataframe = pd.read_csv(
        caminho_arquivo,
        encoding="utf-8",
        dtype={"codigo_ibge": str},
    )

    colunas_numericas = [
        coluna for coluna in dataframe.columns if coluna not in COLUNAS_TEXTO
    ]

    dataframe[colunas_numericas] = (
        dataframe[colunas_numericas]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    dataframe["flag"] = dataframe["flag"].fillna("").str.strip()
    dataframe["corede"] = dataframe["corede"].fillna("Não informado")

    # A sinalização "não homologado com impacto registrado" apenas repete a
    # coluna "situacao", então só interessam as inconsistências de verdade.
    dataframe["sinalizacao_fonte"] = dataframe["flag"].where(
        dataframe["flag"].str.lower() != FLAG_REDUNDANTE, ""
    )

    dataframe["valor_total_rs"] = dataframe["vpc_valor_rs"] + dataframe["sosrs_valor_rs"]

    dataframe["tem_impacto"] = (
        (dataframe["pop_atingida"] > 0)
        | (dataframe["domicilios_atingidos"] > 0)
        | (dataframe["enderecos_atingidos"] > 0)
        | (dataframe["cad_familias_atingidas"] > 0)
        | (dataframe["cnpjs_atingidos"] > 0)
        | (dataframe["equipamentos_atingidos"] > 0)
        | (dataframe["km_atingidos"] > 0)
        | (dataframe["vpc_auxilios"] > 0)
        | (dataframe["sosrs_auxilios"] > 0)
    )

    # Compara proporções (e não valores absolutos), o que neutraliza o efeito de
    # municípios com muitas casas de veraneio, onde há mais domicílios do que
    # habitantes. Marca quando a fatia de domicílios atingidos é 3x ou mais a
    # fatia de pessoas atingidas.
    dataframe["divergencia_proporcao"] = (dataframe["domicilios_atingidos"] >= 5) & (
        (dataframe["pop_atingida"] == 0)
        | (dataframe["pct_domicilios_atingidos"] >= 3 * dataframe["pct_pop_atingida"])
    )

    dataframe["situacao"] = pd.Categorical(
        dataframe["situacao"],
        categories=ORDEM_SITUACAO,
        ordered=True,
    )

    return dataframe.sort_values("municipio").reset_index(drop=True)


df = carregar_dados()


# -----------------------------------------------------------------------------
# Cabeçalho
# -----------------------------------------------------------------------------

st.title("🗺️ Municípios atingidos no Rio Grande do Sul")

st.markdown(
    """
    Registro consolidado do impacto por município: pessoas, domicílios,
    endereços, empresas, vias e auxílios repassados, com a situação de cada
    município (calamidade, emergência ou não homologado).
    """
)


# -----------------------------------------------------------------------------
# Filtros
# -----------------------------------------------------------------------------

with st.container():
    situacoes_selecionadas = st.multiselect(
        "Situação",
        options=ORDEM_SITUACAO,
        default=ORDEM_SITUACAO,
    )

    coredes_disponiveis = sorted(df["corede"].unique())
    coredes_selecionados = st.multiselect(
        "Região (COREDE)",
        options=coredes_disponiveis,
        default=coredes_disponiveis,
    )

    apenas_impacto = st.checkbox(
        "Somente municípios com impacto registrado",
        value=True,
    )

df_filtrado = df[
    df["situacao"].isin(situacoes_selecionadas)
    & df["corede"].isin(coredes_selecionados)
].copy()

if apenas_impacto:
    df_filtrado = df_filtrado[df_filtrado["tem_impacto"]].copy()

if df_filtrado.empty:
    st.info("Nenhum município corresponde aos filtros selecionados.")
    st.stop()


# -----------------------------------------------------------------------------
# Indicadores principais
# -----------------------------------------------------------------------------

st.subheader("Resumo do impacto")

linha1 = st.columns(5)

linha1 = st.columns(5)

linha1[0].metric("Municípios", formatar_numero(len(df_filtrado)))
linha1[1].metric(
    "Pessoas atingidas", formatar_numero(df_filtrado["pop_atingida"].sum())
)
linha1[2].metric(
    "Domicílios atingidos", formatar_numero(df_filtrado["domicilios_atingidos"].sum())
)
linha1[3].metric(
    "Endereços atingidos", formatar_numero(df_filtrado["enderecos_atingidos"].sum())
)
linha1[4].metric(
    "Pessoas no CadÚnico atingidas",
    formatar_numero(df_filtrado["cad_pessoas_atingidas"].sum()),
)

linha2 = st.columns(5)

linha2[0].metric(
    "CNPJs atingidos",
    formatar_numero(df_filtrado["cnpjs_atingidos"].sum())
)
linha2[1].metric(
    "Equipamentos atingidos",
    formatar_numero(df_filtrado["equipamentos_atingidos"].sum()),
)
linha2[2].metric(
    "Km atingidos",
    formatar_numero(df_filtrado["km_atingidos"].sum())
)
linha2[3].metric(
    "Valor repassado (VPC + SOS RS)",
    formatar_moeda(df_filtrado["valor_total_rs"].sum()),
)


# -----------------------------------------------------------------------------
# Concentração do impacto (barras + percentual acumulado)
# -----------------------------------------------------------------------------

st.header(
    "Onde o impacto se concentra",
    divider="gray",
)

controle1, controle2 = st.columns([2, 1])

with controle1:
    criterio_grafico = st.selectbox(
        "Indicador",
        options=list(METRICAS.keys()),
        key="indicador_concentracao",
    )

with controle2:
    quantidade_ranking = st.select_slider(
        "Municípios exibidos",
        options=[5, 10, 15, 20, 30],
        value=10,
        key="quantidade_concentracao",
    )

coluna_grafico = METRICAS[criterio_grafico]

df_ordenado = (
    df_filtrado[df_filtrado[coluna_grafico] > 0]
    .sort_values(coluna_grafico, ascending=False)
    .reset_index(drop=True)
)

if df_ordenado.empty:
    st.info("Nenhum município tem valor registrado para este indicador.")
else:
    total_indicador = df_ordenado[coluna_grafico].sum()

    # O acumulado é calculado sobre todos os municípios; o gráfico mostra só o topo.
    df_ordenado["percentual"] = df_ordenado[coluna_grafico] / total_indicador
    df_ordenado["acumulado"] = df_ordenado["percentual"].cumsum()

    df_topo = df_ordenado.head(quantidade_ranking).copy()
    df_topo["situacao"] = df_topo["situacao"].astype(str)

    st.caption(
        f"Os {len(df_topo)} municípios do gráfico concentram "
        f"**{formatar_percentual(df_topo['acumulado'].iloc[-1])}** de "
        f"{criterio_grafico.lower()}, entre {len(df_ordenado)} municípios "
        f"com valor registrado."
    )

    base = alt.Chart(df_topo).encode(
        x=alt.X(
            "municipio:N",
            title=None,
            sort=None,
            axis=alt.Axis(labelAngle=-40, labelLimit=160),
        )
    )

    barras = base.mark_bar(
        cornerRadiusTopLeft=4,
        cornerRadiusTopRight=4,
    ).encode(
        y=alt.Y(f"{coluna_grafico}:Q", title=criterio_grafico),
        color=alt.Color("situacao:N", title="Situação", scale=ESCALA_SITUACAO),
        tooltip=[
            alt.Tooltip("municipio:N", title="Município"),
            alt.Tooltip("situacao:N", title="Situação"),
            alt.Tooltip(f"{coluna_grafico}:Q", title=criterio_grafico, format=",.0f"),
            alt.Tooltip("percentual:Q", title="% do total", format=".1%"),
            alt.Tooltip("acumulado:Q", title="% acumulado", format=".1%"),
        ],
    )

    if len(df_topo) <= 15:
        rotulos = base.mark_text(
            dy=-6,
            baseline="bottom",
            fontSize=11,
            color="#6B7280",
        ).encode(
            y=alt.Y(f"{coluna_grafico}:Q", title=criterio_grafico),
            text=alt.Text(f"{coluna_grafico}:Q", format=",.0f"),
        )
        camada_barras = alt.layer(barras, rotulos)
    else:
        camada_barras = barras

    grafico_concentracao = (
        alt.layer(camada_barras)
        .properties(height=420)
    )

    st.altair_chart(grafico_concentracao, use_container_width=True)


# -----------------------------------------------------------------------------
# Absoluto x proporcional
# -----------------------------------------------------------------------------

st.header(
    "Tamanho do município x parcela da população atingida",
    divider="gray",
)

st.caption(
    "Cada bolha é um município (tamanho = pessoas atingidas). No alto à esquerda "
    "estão os municípios pequenos atingidos quase por inteiro. À direita estão os "
    "grandes, onde o número absoluto é alto mesmo com parcela menor."
)

df_prop = df_filtrado[df_filtrado["pop_atingida"] > 0].copy()
df_prop["situacao"] = df_prop["situacao"].astype(str)

if df_prop.empty:
    st.info("Nenhum município tem pessoas atingidas nos filtros selecionados.")
else:
    grafico_prop = (
        alt.Chart(df_prop)
        .mark_circle(opacity=0.7)
        .encode(
            x=alt.X(
                "pop_total:Q",
                title="População total do município (escala logarítmica)",
                scale=alt.Scale(type="log"),
            ),
            y=alt.Y(
                "pct_pop_atingida:Q",
                title="% da população atingida",
                scale=alt.Scale(domain=[0, 100]),
            ),
            size=alt.Size(
                "pop_atingida:Q",
                title="Pessoas atingidas",
                scale=alt.Scale(range=[30, 1500]),
            ),
            color=alt.Color("situacao:N", title="Situação", scale=ESCALA_SITUACAO),
            tooltip=[
                alt.Tooltip("municipio:N", title="Município"),
                alt.Tooltip("corede:N", title="Região"),
                alt.Tooltip("situacao:N", title="Situação"),
                alt.Tooltip("pop_atingida:Q", title="Pessoas atingidas", format=",.0f"),
                alt.Tooltip("pop_total:Q", title="População total", format=",.0f"),
                alt.Tooltip("pct_pop_atingida:Q", title="% atingida", format=".1f"),
            ],
        )
        .properties(height=450)
        .interactive()
    )

    st.altair_chart(grafico_prop, use_container_width=True)

# -----------------------------------------------------------------------------
# Composição por situação
# -----------------------------------------------------------------------------

st.header(
    "Como cada situação contribui para o impacto",
    divider="gray",
)

COMPOSICAO = {
    "Municípios": "municipios",
    "Pessoas atingidas": "pop_atingida",
    "Domicílios atingidos": "domicilios_atingidos",
    "Pessoas no CadÚnico": "cad_pessoas_atingidas",
    "CNPJs atingidos": "cnpjs_atingidos",
    "Km atingidos": "km_atingidos",
    "Valor repassado (R$)": "valor_total_rs",
}

df_situacao = (
    df_filtrado.assign(situacao=df_filtrado["situacao"].astype(str))
    .groupby("situacao", as_index=False)
    .agg(
        municipios=("municipio", "count"),
        pop_atingida=("pop_atingida", "sum"),
        domicilios_atingidos=("domicilios_atingidos", "sum"),
        cad_pessoas_atingidas=("cad_pessoas_atingidas", "sum"),
        cnpjs_atingidos=("cnpjs_atingidos", "sum"),
        km_atingidos=("km_atingidos", "sum"),
        valor_total_rs=("valor_total_rs", "sum"),
    )
)

registros_composicao = []

for rotulo, coluna in COMPOSICAO.items():
    total = df_situacao[coluna].sum()

    for _, linha in df_situacao.iterrows():
        registros_composicao.append(
            {
                "indicador": rotulo,
                "situacao": linha["situacao"],
                "ordem": ORDEM_SITUACAO.index(linha["situacao"]),
                "valor": linha[coluna],
                "percentual": (linha[coluna] / total) if total > 0 else 0,
            }
        )

df_composicao = pd.DataFrame(registros_composicao)

grafico_composicao = (
    alt.Chart(df_composicao)
    .mark_bar()
    .encode(
        x=alt.X(
            "valor:Q",
            stack="normalize",
            title="Participação no total",
            axis=alt.Axis(format="%"),
        ),
        y=alt.Y("indicador:N", title=None, sort=list(COMPOSICAO.keys())),
        color=alt.Color("situacao:N", title="Situação", scale=ESCALA_SITUACAO),
        order=alt.Order("ordem:Q", sort="ascending"),
        tooltip=[
            alt.Tooltip("indicador:N", title="Indicador"),
            alt.Tooltip("situacao:N", title="Situação"),
            alt.Tooltip("valor:Q", title="Valor", format=",.0f"),
            alt.Tooltip("percentual:Q", title="Participação", format=".1%"),
        ],
    )
    .properties(height=300)
)

st.altair_chart(grafico_composicao, use_container_width=True)

st.dataframe(
    df_situacao.rename(
        columns={
            "situacao": "Situação",
            "municipios": "Municípios",
            "pop_atingida": "Pessoas atingidas",
            "domicilios_atingidos": "Domicílios atingidos",
            "cad_pessoas_atingidas": "Pessoas no CadÚnico",
            "cnpjs_atingidos": "CNPJs atingidos",
            "km_atingidos": "Km atingidos",
            "valor_total_rs": "Valor repassado (R$)",
        }
    ),
    hide_index=True,
    use_container_width=True,
    column_config={
        "Valor repassado (R$)": st.column_config.NumberColumn(format="R$ %d"),
    },
)


# -----------------------------------------------------------------------------
# Auxílios repassados
# -----------------------------------------------------------------------------

st.header(
    "Auxílios repassados",
    divider="gray",
)

total_vpc_qtd = df_filtrado["vpc_auxilios"].sum()
total_vpc_valor = df_filtrado["vpc_valor_rs"].sum()
total_sos_qtd = df_filtrado["sosrs_auxilios"].sum()
total_sos_valor = df_filtrado["sosrs_valor_rs"].sum()

aux1, aux2 = st.columns(2)

aux1.metric(
    "VPC",
    f"{formatar_numero(total_vpc_qtd)} auxílios",
    formatar_moeda(total_vpc_valor),
    delta_color="off",
)
aux2.metric(
    "SOS RS",
    f"{formatar_numero(total_sos_qtd)} auxílios",
    formatar_moeda(total_sos_valor),
    delta_color="off",
)

quantidade_auxilios = st.select_slider(
    "Municípios exibidos",
    options=[5, 10, 15, 20, 30],
    value=10,
    key="quantidade_auxilios",
)

df_aux = (
    df_filtrado[df_filtrado["valor_total_rs"] > 0]
    .sort_values("valor_total_rs", ascending=False)
    .head(quantidade_auxilios)
)

if df_aux.empty:
    st.info("Nenhum município tem auxílios registrados nos filtros selecionados.")
else:
    registros_aux = []

    for _, linha in df_aux.iterrows():
        registros_aux.append(
            {
                "municipio": linha["municipio"],
                "programa": "VPC",
                "valor": linha["vpc_valor_rs"],
                "quantidade": linha["vpc_auxilios"],
                "total_municipio": linha["valor_total_rs"],
            }
        )
        registros_aux.append(
            {
                "municipio": linha["municipio"],
                "programa": "SOS RS",
                "valor": linha["sosrs_valor_rs"],
                "quantidade": linha["sosrs_auxilios"],
                "total_municipio": linha["valor_total_rs"],
            }
        )

    df_aux_longo = pd.DataFrame(registros_aux)

    grafico_aux = (
        alt.Chart(df_aux_longo)
        .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
        .encode(
            x=alt.X("valor:Q", title="Valor repassado (R$)", axis=alt.Axis(format=",.0f")),
            y=alt.Y(
                "municipio:N",
                title=None,
                sort=alt.EncodingSortField(
                    field="total_municipio", op="max", order="descending"
                ),
            ),
            color=alt.Color(
                "programa:N",
                title="Programa",
                scale=alt.Scale(
                    domain=["VPC", "SOS RS"],
                    range=["#2563EB", "#10B981"],
                ),
            ),
            tooltip=[
                alt.Tooltip("municipio:N", title="Município"),
                alt.Tooltip("programa:N", title="Programa"),
                alt.Tooltip("quantidade:Q", title="Auxílios", format=",.0f"),
                alt.Tooltip("valor:Q", title="Valor (R$)", format=",.0f"),
            ],
        )
        .properties(height=max(300, len(df_aux) * 26))
    )

    st.altair_chart(grafico_aux, use_container_width=True)

# -----------------------------------------------------------------------------
# Tabela detalhada
# -----------------------------------------------------------------------------

st.header(
    "Dados por município",
    divider="gray",
)

with st.expander("Ver tabela completa", expanded=False):
    df_tabela = df_filtrado[
        [
            "codigo_ibge",
            "municipio",
            "corede",
            "situacao",
            "pop_atingida",
            "pct_pop_atingida",
            "domicilios_atingidos",
            "pct_domicilios_atingidos",
            "enderecos_atingidos",
            "cad_pessoas_atingidas",
            "cnpjs_atingidos",
            "equipamentos_atingidos",
            "km_atingidos",
            "vpc_auxilios",
            "sosrs_auxilios",
            "valor_total_rs",
            "sinalizacao_fonte",
        ]
    ].sort_values("pop_atingida", ascending=False)

    df_tabela["situacao"] = df_tabela["situacao"].astype(str)

    st.dataframe(
        df_tabela.rename(
            columns={
                "codigo_ibge": "Código IBGE",
                "municipio": "Município",
                "corede": "Região (COREDE)",
                "situacao": "Situação",
                "pop_atingida": "Pessoas atingidas",
                "pct_pop_atingida": "% da população",
                "domicilios_atingidos": "Domicílios atingidos",
                "pct_domicilios_atingidos": "% dos domicílios",
                "enderecos_atingidos": "Endereços atingidos",
                "cad_pessoas_atingidas": "Pessoas no CadÚnico",
                "cnpjs_atingidos": "CNPJs atingidos",
                "equipamentos_atingidos": "Equipamentos atingidos",
                "km_atingidos": "Km atingidos",
                "vpc_auxilios": "Auxílios VPC",
                "sosrs_auxilios": "Auxílios SOS RS",
                "valor_total_rs": "Valor repassado (R$)",
                "sinalizacao_fonte": "Sinalização da fonte",
            }
        ),
        hide_index=True,
        use_container_width=True,
        column_config={
            "% da população": st.column_config.ProgressColumn(
                "% da população", min_value=0, max_value=100, format="%.1f%%"
            ),
            "% dos domicílios": st.column_config.ProgressColumn(
                "% dos domicílios", min_value=0, max_value=100, format="%.1f%%"
            ),
            "Valor repassado (R$)": st.column_config.NumberColumn(format="R$ %d"),
        },
    )

    st.download_button(
        "Baixar dados filtrados (CSV)",
        data=df_tabela.to_csv(index=False).encode("utf-8-sig"),
        file_name="municipios_atingidos_filtrado.csv",
        mime="text/csv",
    )


# -----------------------------------------------------------------------------
# Limitações dos dados
# -----------------------------------------------------------------------------

st.header(
    "Limitações dos dados",
    divider="gray",
)

st.warning(
    """
    **Atenção ao interpretar os resultados**

    Os valores são registros consolidados por município e não representam
    medições em tempo real. Alguns indicadores vêm de fontes diferentes, e por
    isso podem divergir entre si, como domicílios e pessoas atingidas em alguns
    municípios. Em municípios com muitas casas de veraneio, o número de domicílios
    pode superar o de habitantes sem que haja erro. Em quilômetros atingidos, os
    municípios sem informação na fonte aparecem com valor zero. A coluna
    "situação" é um status administrativo e não mede o tamanho do impacto.

    Os valores devem ser utilizados para análise e planejamento, não como
    substitutos de alertas oficiais ou orientações da Defesa Civil.
    """
)

st.caption("Fonte dos dados: arquivo muprs_limpo.csv.")
