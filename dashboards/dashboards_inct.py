import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


# -----------------------------------------------------------------------------
# Configuração da página
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Impacto da elevação do Guaíba",
    page_icon="🌊",
    layout="wide",
)


# -----------------------------------------------------------------------------
# Carregamento e tratamento dos dados
# -----------------------------------------------------------------------------

@st.cache_data
def carregar_dados():
    raiz_projeto = Path(__file__).resolve().parent.parent
    caminho_arquivo = raiz_projeto / "dados" / "processados" / "data_alterado.json"

    with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
        dados_json = json.load(arquivo)

    registros = []

    for chave_nivel, bairros in dados_json.items():
        nivel = float(
            chave_nivel
            .replace("m", "")
            .replace("_", ".")
        )

        for bairro, dados_bairro in bairros.items():
            registros.append(
                {
                    "nivel": nivel,
                    "bairro": bairro,
                    "predios_afetados": dados_bairro["affected_buildings"],
                    "total_predios": dados_bairro["total_buildings"],
                    "percentual_predios_afetados": dados_bairro["percentage"],
                    "populacao": dados_bairro["population"],
                    "populacao_afetada": dados_bairro["affected_population"],
                }
            )

    dataframe = pd.DataFrame(registros)

    dataframe["nivel"] = pd.to_numeric(
        dataframe["nivel"],
        errors="coerce",
    )

    colunas_numericas = [
        "predios_afetados",
        "total_predios",
        "percentual_predios_afetados",
        "populacao",
        "populacao_afetada",
    ]

    dataframe[colunas_numericas] = (
        dataframe[colunas_numericas]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    return dataframe.sort_values(["nivel", "bairro"])


df = carregar_dados()


# -----------------------------------------------------------------------------
# Cabeçalho
# -----------------------------------------------------------------------------

st.title("🌊 Impacto da elevação do nível do Guaíba")

st.markdown(
    """
    Explore os impactos estimados da elevação do nível do Guaíba sobre a
    população, os prédios e os bairros de Porto Alegre.
    """
)


# -----------------------------------------------------------------------------
# Controle do nível do Guaíba
# -----------------------------------------------------------------------------

nivel_selecionado = st.slider(
    "Selecione o nível do Guaíba",
    min_value=3.0,
    max_value=10.0,
    value=5.4,
    step=0.1,
    format="%.1f m",
)

# Evita problemas de precisão com números decimais.
nivel_selecionado = round(nivel_selecionado, 1)

df_nivel = df[
    df["nivel"].round(1) == nivel_selecionado
].copy()

df_bairros_atingidos = df_nivel[
    (df_nivel["predios_afetados"] > 0)
    | (df_nivel["populacao_afetada"] > 0)
].copy()


# -----------------------------------------------------------------------------
# Indicadores principais
# -----------------------------------------------------------------------------

pessoas_afetadas = int(df_nivel["populacao_afetada"].sum())
predios_afetados = int(df_nivel["predios_afetados"].sum())
bairros_atingidos = int(df_bairros_atingidos["bairro"].nunique())

st.subheader(f"Impacto estimado para o nível de {nivel_selecionado:.1f} m")

coluna1, coluna2, coluna3 = st.columns(3)

with coluna1:
    st.metric(
        label="Pessoas afetadas",
        value=f"{pessoas_afetadas:,.0f}".replace(",", "."),
    )

with coluna2:
    st.metric(
        label="Prédios afetados",
        value=f"{predios_afetados:,.0f}".replace(",", "."),
    )

with coluna3:
    st.metric(
        label="Bairros atingidos",
        value=f"{bairros_atingidos}",
    )


# -----------------------------------------------------------------------------
# Gráfico de percentual de prédios afetados
# -----------------------------------------------------------------------------

st.header(
    "Percentual de prédios afetados por bairro",
    divider="gray",
)

if df_bairros_atingidos.empty:
    st.info("Nenhum bairro é atingido no nível selecionado.")
else:
    df_percentual = (
        df_bairros_atingidos[
            [
                "bairro",
                "percentual_predios_afetados",
                "predios_afetados",
                "total_predios",
            ]
        ]
        .sort_values(
            "percentual_predios_afetados",
            ascending=False,
        )
    )

    grafico_percentual = (
        alt.Chart(df_percentual)
        .mark_bar(
            cornerRadiusTopRight=4,
            cornerRadiusBottomRight=4,
        )
        .encode(
            x=alt.X(
                "percentual_predios_afetados:Q",
                title="Prédios afetados (%)",
                scale=alt.Scale(domain=[0, 100]),
            ),
            y=alt.Y(
                "bairro:N",
                title=None,
                sort="-x",
            ),
            color=alt.Color(
                "percentual_predios_afetados:Q",
                title="Percentual",
                scale=alt.Scale(
                    domain=[0, 25, 50, 75, 100],
                    range=[
                        "#DCEAF7",
                        "#87BCE8",
                        "#F9D976",
                        "#F28E5B",
                        "#C73E3A",
                    ],
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "bairro:N",
                    title="Bairro",
                ),
                alt.Tooltip(
                    "percentual_predios_afetados:Q",
                    title="Prédios afetados",
                    format=".1f",
                ),
                alt.Tooltip(
                    "predios_afetados:Q",
                    title="Quantidade afetada",
                    format=",.0f",
                ),
                alt.Tooltip(
                    "total_predios:Q",
                    title="Total de prédios",
                    format=",.0f",
                ),
            ],
        )
        .properties(
            height=max(450, len(df_percentual) * 24)
        )
    )

    st.altair_chart(
        grafico_percentual,
        use_container_width=True,
    )


# -----------------------------------------------------------------------------
# Curva da população afetada
# -----------------------------------------------------------------------------

st.header(
    "População afetada por nível do Guaíba",
    divider="gray",
)

df_curva = (
    df.groupby("nivel", as_index=False)
    .agg(
        populacao_afetada=("populacao_afetada", "sum")
    )
    .sort_values("nivel")
)

linha_populacao = (
    alt.Chart(df_curva)
    .mark_line(
        color="#2563EB",
        strokeWidth=3,
        interpolate="monotone",
    )
    .encode(
        x=alt.X(
            "nivel:Q",
            title="Nível do Guaíba (m)",
            scale=alt.Scale(domain=[3.0, 10.0]),
        ),
        y=alt.Y(
            "populacao_afetada:Q",
            title="Pessoas afetadas",
        ),
        tooltip=[
            alt.Tooltip(
                "nivel:Q",
                title="Nível",
                format=".1f",
            ),
            alt.Tooltip(
                "populacao_afetada:Q",
                title="Pessoas afetadas",
                format=",.0f",
            ),
        ],
    )
)

pontos_populacao = (
    alt.Chart(df_curva)
    .mark_circle(
        color="#2563EB",
        size=45,
    )
    .encode(
        x="nivel:Q",
        y="populacao_afetada:Q",
        tooltip=[
            alt.Tooltip(
                "nivel:Q",
                title="Nível",
                format=".1f",
            ),
            alt.Tooltip(
                "populacao_afetada:Q",
                title="Pessoas afetadas",
                format=",.0f",
            ),
        ],
    )
)

# O nível recorde está entre os pontos de 5,3 m e 5,4 m da base.
nivel_recorde = 5.35

linha_recorde = (
    alt.Chart(
        pd.DataFrame(
            {
                "nivel_recorde": [nivel_recorde],
            }
        )
    )
    .mark_rule(
        color="#DC2626",
        strokeWidth=2,
        strokeDash=[6, 4],
    )
    .encode(
        x=alt.X(
            "nivel_recorde:Q",
        )
    )
)

texto_recorde = (
    alt.Chart(
        pd.DataFrame(
            {
                "nivel_recorde": [nivel_recorde],
                "texto": ["Recorde de maio de 2024: 5,35 m"],
            }
        )
    )
    .mark_text(
        align="left",
        baseline="top",
        dx=7,
        dy=8,
        color="#DC2626",
        fontWeight="bold",
    )
    .encode(
        x="nivel_recorde:Q",
        y=alt.value(10),
        text="texto:N",
    )
)

grafico_curva = (
    linha_populacao
    + pontos_populacao
    + linha_recorde
    + texto_recorde
).properties(
    height=450
).interactive()

st.altair_chart(
    grafico_curva,
    use_container_width=True,
)


# -----------------------------------------------------------------------------
# Ranking dos bairros mais afetados
# -----------------------------------------------------------------------------

st.header(
    f"Ranking dos bairros mais afetados em {nivel_selecionado:.1f} m",
    divider="gray",
)

quantidade_ranking = st.selectbox(
    "Quantidade de bairros no ranking",
    options=[5, 10, 15, 20],
    index=1,
)

criterio_ranking = st.radio(
    "Ordenar o ranking por:",
    options=[
        "Pessoas afetadas",
        "Prédios afetados",
        "Percentual de prédios afetados",
    ],
    horizontal=True,
)

mapa_criterios = {
    "Pessoas afetadas": "populacao_afetada",
    "Prédios afetados": "predios_afetados",
    "Percentual de prédios afetados": "percentual_predios_afetados",
}

coluna_ranking = mapa_criterios[criterio_ranking]

df_ranking = (
    df_bairros_atingidos.sort_values(
        by=[
            coluna_ranking,
            "populacao_afetada",
            "predios_afetados",
        ],
        ascending=False,
    )
    .head(quantidade_ranking)
    .copy()
)

df_ranking.insert(
    0,
    "posição",
    range(1, len(df_ranking) + 1),
)

df_ranking_exibicao = df_ranking[
    [
        "posição",
        "bairro",
        "populacao_afetada",
        "predios_afetados",
        "percentual_predios_afetados",
    ]
].rename(
    columns={
        "posição": "Posição",
        "bairro": "Bairro",
        "populacao_afetada": "Pessoas afetadas",
        "predios_afetados": "Prédios afetados",
        "percentual_predios_afetados": "Prédios afetados (%)",
    }
)

st.dataframe(
    df_ranking_exibicao,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Posição": st.column_config.NumberColumn(
            "Posição",
            format="%dº",
        ),
        "Pessoas afetadas": st.column_config.NumberColumn(
            "Pessoas afetadas",
            format="%d",
        ),
        "Prédios afetados": st.column_config.NumberColumn(
            "Prédios afetados",
            format="%d",
        ),
        "Prédios afetados (%)": st.column_config.ProgressColumn(
            "Prédios afetados (%)",
            min_value=0,
            max_value=100,
            format="%d%%",
        ),
    },
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

    As informações apresentadas são estimativas produzidas a partir dos
    dados disponíveis e não representam medições em tempo real. O modelo
    considera níveis do Guaíba em intervalos de 0,1 m e pode não incorporar
    fatores como falhas ou atuação de sistemas de proteção, condições de
    drenagem, duração do alagamento, chuvas locais e alterações recentes
    na ocupação urbana.

    Os valores devem ser utilizados para análise e planejamento, não como
    substitutos de alertas oficiais ou orientações da Defesa Civil.
    """
)

st.caption(
    "Fonte dos dados: arquivo data_alterado.json. \n"
    "Nível recorde destacado: 5,35 m, registrado em maio de 2024."
)