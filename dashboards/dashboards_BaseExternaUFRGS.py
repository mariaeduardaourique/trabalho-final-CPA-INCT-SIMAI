import json
import unicodedata
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


# -----------------------------------------------------------------------------
# Configuração da página
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="A cheia de 2024 e a simulação",
    page_icon="🛰️",
    layout="wide",
)

# Esta página fica em pages/, então a raiz do projeto é a pasta acima.
RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "dados" / "processados"

NIVEL_MANCHA = 5.3  # a mancha da UFRGS corresponde ao nível de 5,3 m
IOU_SATELITE_MANCHA = 80.61  # calculado em scripts/fonteexterna.ipynb

CAMADAS = {
    "Mancha de inundação de 5,3 m": "pct_mancha",
    "Água observada por satélite em 06/05/2024": "pct_satelite",
}

INDICADORES_INCT = {
    "% de prédios afetados": "pct_predios_inct",
    "% da população afetada": "pct_populacao_inct",
}

# Nomes que mudam entre a malha de bairros da UFRGS e o INCT,
# depois de tirar acentos e apóstrofos.
EQUIVALENCIAS = {
    "CEL APARICIO BORGES": "CORONEL APARICIO BORGES",
    "SAO JOSE": "VILA SAO JOSE",
}

AZUL = "#2563EB"
LARANJA = "#E8833A"
CINZA = "#9CA3AF"


# -----------------------------------------------------------------------------
# Funções auxiliares
# -----------------------------------------------------------------------------

def chave_bairro(nome):
    """Maiúsculas, sem acento e sem apóstrofo, para cruzar as bases."""
    texto = unicodedata.normalize("NFKD", str(nome))
    texto = texto.encode("ascii", "ignore").decode()
    texto = " ".join(texto.upper().replace("'", "").split())
    return EQUIVALENCIAS.get(texto, texto)


def formatar_numero(valor, casas=0):
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


# -----------------------------------------------------------------------------
# Carregamento e tratamento dos dados
# -----------------------------------------------------------------------------

@st.cache_data
def carregar_inct(nivel):
    """Dados do INCT (já limpos) para um nível.

    Aceita o data_alterado.json nos dois formatos usados pela equipe:
    aninhado ({"5_3m": {bairro: {...}}}) ou longo ([{"nivel_m": 5.3, ...}]).
    """
    with open(PASTA_DADOS / "data_alterado.json", encoding="utf-8") as arquivo:
        dados_json = json.load(arquivo)

    if isinstance(dados_json, dict):
        chave_nivel = f"{nivel:.1f}".replace(".", "_") + "m"
        registros = [
            {"bairro": bairro, **valores}
            for bairro, valores in dados_json[chave_nivel].items()
        ]
    else:
        registros = [
            linha for linha in dados_json
            if round(float(linha["nivel_m"]), 1) == nivel
        ]

    df = pd.DataFrame(registros)[
        [
            "bairro",
            "affected_buildings",
            "total_buildings",
            "population",
            "affected_population",
        ]
    ]

    # Recalcula os percentuais a partir das contagens.
    df["pct_predios_inct"] = (
        df["affected_buildings"] / df["total_buildings"] * 100
    )
    df["pct_populacao_inct"] = (
        df["affected_population"] / df["population"] * 100
    )
    df["chave"] = df["bairro"].apply(chave_bairro)

    return df.rename(columns={"bairro": "bairro_inct"})


@st.cache_data
def carregar_ufrgs():
    """Cobertura de cada bairro pelas duas camadas da UFRGS."""
    mancha = pd.read_csv(
        PASTA_DADOS / "ufrgs_cobertura_530cm_por_bairro.csv",
        encoding="utf-8-sig",
    )
    satelite = pd.read_csv(
        PASTA_DADOS / "ufrgs_area_por_bairro.csv",
        encoding="utf-8-sig",
    )

    df = mancha.merge(satelite, on="bairro", how="left")
    df["area_agua_km2"] = df["area_agua_km2"].fillna(0)

    df = df.rename(
        columns={
            "area_mancha_km2": "area_mancha_km2",
            "area_agua_km2": "area_satelite_km2",
            "percentual_cobertura": "pct_mancha",
        }
    )
    df["pct_satelite"] = (
        df["area_satelite_km2"] / df["area_bairro_km2"] * 100
    ).clip(upper=100)
    df["chave"] = df["bairro"].apply(chave_bairro)

    return df.rename(columns={"bairro": "bairro_ufrgs"})


@st.cache_data
def montar_base():
    ufrgs = carregar_ufrgs()
    inct = carregar_inct(NIVEL_MANCHA)

    base = ufrgs.merge(inct, on="chave", how="left", indicator=True)

    # Nome de exibição: o do INCT, que tem acentos.
    base["bairro"] = base["bairro_inct"].fillna(
        base["bairro_ufrgs"].str.title()
    )

    sem_par_ufrgs = base.loc[base["_merge"] == "left_only", "bairro_ufrgs"]
    sem_par_inct = inct.loc[
        ~inct["chave"].isin(ufrgs["chave"]), "bairro_inct"
    ]

    base = base[base["_merge"] == "both"].drop(columns="_merge")

    return base, sorted(sem_par_ufrgs), sorted(sem_par_inct)


df, sem_par_ufrgs, sem_par_inct = montar_base()


# -----------------------------------------------------------------------------
# Cabeçalho
# -----------------------------------------------------------------------------

st.title("🛰️ O que a cheia de maio de 2024 acrescenta à simulação?")

st.markdown(
    """
    A simulação do INCT SiMAI mostra quais prédios ficam alagados em cada
    nível do Guaíba. Esta tela coloca ao lado dela o que foi **observado**
    na cheia de 2024, a partir dos dados geográficos da UFRGS: a mancha de
    inundação associada a 5,3 m e a água vista por satélite em 06/05/2024.
    """
)

st.info(
    """
    As duas bases medem coisas diferentes: a UFRGS mede a **área** do bairro
    coberta pela água; o INCT estima **prédios e pessoas** afetados. Um bairro
    com muitos parques, várzeas ou ilhas pode ter grande área alagada e poucos
    prédios atingidos. Por isso as diferenças não indicam erro de nenhuma das
    duas bases.
    """
)


# -----------------------------------------------------------------------------
# Filtros
# -----------------------------------------------------------------------------

coluna_filtro1, coluna_filtro2 = st.columns(2)

with coluna_filtro1:
    nome_camada = st.radio(
        "Base observada (UFRGS)",
        options=list(CAMADAS),
        horizontal=True,
    )

with coluna_filtro2:
    nome_indicador = st.radio(
        "Indicador da simulação (INCT, 5,3 m)",
        options=list(INDICADORES_INCT),
        horizontal=True,
    )

col_camada = CAMADAS[nome_camada]
col_inct = INDICADORES_INCT[nome_indicador]

bairros_destacados = st.multiselect(
    "Destacar bairros",
    options=sorted(df["bairro"]),
    placeholder="Escolha um ou mais bairros",
)

somente_atingidos = st.toggle(
    "Mostrar apenas bairros atingidos em pelo menos uma das bases",
    value=True,
)

df_filtro = df.copy()
if somente_atingidos:
    df_filtro = df_filtro[
        (df_filtro[col_camada] > 0) | (df_filtro[col_inct] > 0)
    ]

df_filtro["destaque"] = df_filtro["bairro"].isin(bairros_destacados)
df_filtro["diferenca_pp"] = df_filtro[col_inct] - df_filtro[col_camada]


# -----------------------------------------------------------------------------
# Indicadores principais
# -----------------------------------------------------------------------------

coluna_area = (
    "area_mancha_km2" if col_camada == "pct_mancha" else "area_satelite_km2"
)
area_total = df[coluna_area].sum()
bairros_com_agua = int((df[col_camada] > 0).sum())
correlacao = df[col_camada].corr(df[col_inct])

st.subheader("Visão geral")

coluna1, coluna2, coluna3, coluna4 = st.columns(4)

with coluna1:
    st.metric(
        label="Área alagada nos bairros",
        value=f"{formatar_numero(area_total, 1)} km²",
        help=f"Soma da área de cada bairro coberta pela camada: {nome_camada}.",
    )

with coluna2:
    st.metric(
        label="Bairros com água",
        value=f"{bairros_com_agua} de {len(df)}",
    )

with coluna3:
    st.metric(
        label="Satélite e mancha coincidem em",
        value=f"{formatar_numero(IOU_SATELITE_MANCHA, 1)}%",
        help=(
            "Área comum às duas camadas dividida pela área total das duas "
            "(índice IoU), calculada em scripts/fonteexterna.ipynb."
        ),
    )

with coluna4:
    st.metric(
        label="Correlação com o INCT",
        value=formatar_numero(correlacao, 2),
        help=(
            "Correlação de Pearson, entre os bairros, da % coberta pela base "
            "observada e do indicador escolhido da simulação."
        ),
    )


# -----------------------------------------------------------------------------
# Gráfico 1: observado × simulado
# -----------------------------------------------------------------------------

st.header(
    "Observado na cheia × simulado pelo INCT",
    divider="gray",
)

st.caption(
    "Cada ponto é um bairro. Na linha tracejada, as duas bases dão o mesmo "
    "percentual. Acima dela, a simulação indica proporcionalmente mais "
    "prédios ou pessoas afetados do que a área coberta pela água."
)

dicas_bairro = [
    alt.Tooltip("bairro:N", title="Bairro"),
    alt.Tooltip(f"{col_camada}:Q", title=f"Área coberta (%)", format=".1f"),
    alt.Tooltip(f"{col_inct}:Q", title=nome_indicador, format=".1f"),
    alt.Tooltip("affected_population:Q", title="Pessoas afetadas (INCT)", format=",.0f"),
]

diagonal = (
    alt.Chart(pd.DataFrame({"x": [0, 100], "y": [0, 100]}))
    .mark_line(color=CINZA, strokeDash=[6, 4])
    .encode(x="x:Q", y="y:Q")
)

pontos = (
    alt.Chart(df_filtro)
    .mark_circle(size=90, stroke="white", strokeWidth=1)
    .encode(
        x=alt.X(
            f"{col_camada}:Q",
            title=f"Área do bairro coberta: {nome_camada} (%)",
            scale=alt.Scale(domain=[0, 100]),
        ),
        y=alt.Y(
            f"{col_inct}:Q",
            title=f"Simulação INCT a 5,3 m: {nome_indicador}",
            scale=alt.Scale(domain=[0, 100]),
        ),
        color=alt.condition(
            "datum.destaque",
            alt.value(LARANJA),
            alt.value(AZUL),
        ),
        opacity=alt.condition(
            "datum.destaque",
            alt.value(1.0),
            alt.value(0.7 if not bairros_destacados else 0.35),
        ),
        tooltip=dicas_bairro,
    )
)

rotulos = (
    alt.Chart(df_filtro[df_filtro["destaque"]])
    .mark_text(align="left", dx=8, fontWeight="bold", color=LARANJA)
    .encode(
        x=f"{col_camada}:Q",
        y=f"{col_inct}:Q",
        text="bairro:N",
    )
)

st.altair_chart(
    (diagonal + pontos + rotulos).properties(height=480).interactive(),
    use_container_width=True,
)


# -----------------------------------------------------------------------------
# Gráfico 2: bairro a bairro
# -----------------------------------------------------------------------------

st.header(
    "Bairro a bairro: onde as duas bases se aproximam e se afastam",
    divider="gray",
)

ordem = st.radio(
    "Ordenar por",
    options=[
        "Maior diferença entre as bases",
        "Maior área coberta",
        "Maior valor na simulação",
    ],
    horizontal=True,
)

colunas_ordem = {
    "Maior diferença entre as bases": "diferenca_abs",
    "Maior área coberta": col_camada,
    "Maior valor na simulação": col_inct,
}

df_barras = df_filtro.assign(diferenca_abs=df_filtro["diferenca_pp"].abs())
if bairros_destacados:
    df_barras = df_barras[df_barras["destaque"]]
df_barras = df_barras.sort_values(colunas_ordem[ordem], ascending=False).head(25)

ordem_bairros = df_barras["bairro"].tolist()

df_barras_longo = df_barras.melt(
    id_vars=["bairro", "diferenca_pp"],
    value_vars=[col_camada, col_inct],
    var_name="base",
    value_name="percentual",
)
df_barras_longo["base"] = df_barras_longo["base"].map(
    {
        col_camada: "Observado (UFRGS): área coberta",
        col_inct: f"Simulado (INCT): {nome_indicador}",
    }
)

if df_barras_longo.empty:
    st.info("Nenhum bairro para mostrar com os filtros escolhidos.")
else:
    grafico_barras = (
        alt.Chart(df_barras_longo)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            x=alt.X(
                "percentual:Q",
                title="Percentual (%)",
                scale=alt.Scale(domain=[0, 100]),
            ),
            y=alt.Y("bairro:N", title=None, sort=ordem_bairros),
            yOffset=alt.YOffset("base:N"),
            color=alt.Color(
                "base:N",
                title=None,
                scale=alt.Scale(range=[AZUL, LARANJA]),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("bairro:N", title="Bairro"),
                alt.Tooltip("base:N", title="Base"),
                alt.Tooltip("percentual:Q", title="Percentual", format=".1f"),
                alt.Tooltip("diferenca_pp:Q", title="Diferença (p.p.)", format="+.1f"),
            ],
        )
        .properties(height=max(400, len(ordem_bairros) * 34))
    )

    st.altair_chart(grafico_barras, use_container_width=True)

    st.caption(
        "Mostrando até 25 bairros. A diferença está em pontos percentuais "
        "(simulado menos observado)."
    )


# -----------------------------------------------------------------------------
# Gráfico 3: as duas observações da UFRGS
# -----------------------------------------------------------------------------

st.header(
    "Duas formas de observar a cheia: satélite em 06/05 × mancha de 5,3 m",
    divider="gray",
)

quantidade = st.slider(
    "Quantidade de bairros",
    min_value=5,
    max_value=20,
    value=10,
    step=1,
)

df_camadas = (
    df.assign(maior_area=df[["area_mancha_km2", "area_satelite_km2"]].max(axis=1))
    .sort_values("maior_area", ascending=False)
    .head(quantidade)
)
ordem_camadas = df_camadas["bairro"].tolist()

df_camadas_longo = df_camadas.melt(
    id_vars=["bairro"],
    value_vars=["area_satelite_km2", "area_mancha_km2"],
    var_name="camada",
    value_name="area_km2",
)
df_camadas_longo["camada"] = df_camadas_longo["camada"].map(
    {
        "area_satelite_km2": "Satélite em 06/05/2024",
        "area_mancha_km2": "Mancha de 5,3 m",
    }
)

grafico_camadas = (
    alt.Chart(df_camadas_longo)
    .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
    .encode(
        x=alt.X("area_km2:Q", title="Área alagada no bairro (km²)"),
        y=alt.Y("bairro:N", title=None, sort=ordem_camadas),
        yOffset=alt.YOffset("camada:N"),
        color=alt.Color(
            "camada:N",
            title=None,
            scale=alt.Scale(range=[AZUL, CINZA]),
            legend=alt.Legend(orient="top"),
        ),
        tooltip=[
            alt.Tooltip("bairro:N", title="Bairro"),
            alt.Tooltip("camada:N", title="Camada"),
            alt.Tooltip("area_km2:Q", title="Área (km²)", format=".2f"),
        ],
    )
    .properties(height=max(350, quantidade * 34))
)

st.altair_chart(grafico_camadas, use_container_width=True)

st.caption(
    "As duas camadas concordam na maior parte da cidade. As diferenças "
    "aparecem sobretudo no extremo sul (Belém Novo, Lami e Ponta Grossa), "
    "onde há grandes áreas sem ocupação."
)


# -----------------------------------------------------------------------------
# Tabela
# -----------------------------------------------------------------------------

st.header("Dados por bairro", divider="gray")

tabela = df_filtro[
    [
        "bairro",
        "area_bairro_km2",
        "pct_mancha",
        "pct_satelite",
        "pct_predios_inct",
        "pct_populacao_inct",
        "affected_population",
    ]
].sort_values("pct_mancha", ascending=False)

tabela = tabela.rename(
    columns={
        "bairro": "Bairro",
        "area_bairro_km2": "Área do bairro (km²)",
        "pct_mancha": "Mancha 5,3 m (%)",
        "pct_satelite": "Satélite 06/05 (%)",
        "pct_predios_inct": "Prédios afetados INCT (%)",
        "pct_populacao_inct": "População afetada INCT (%)",
        "affected_population": "Pessoas afetadas INCT",
    }
)

st.dataframe(
    tabela,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Área do bairro (km²)": st.column_config.NumberColumn(format="%.2f"),
        "Mancha 5,3 m (%)": st.column_config.ProgressColumn(
            min_value=0, max_value=100, format="%.1f%%"
        ),
        "Satélite 06/05 (%)": st.column_config.ProgressColumn(
            min_value=0, max_value=100, format="%.1f%%"
        ),
        "Prédios afetados INCT (%)": st.column_config.ProgressColumn(
            min_value=0, max_value=100, format="%.1f%%"
        ),
        "População afetada INCT (%)": st.column_config.ProgressColumn(
            min_value=0, max_value=100, format="%.1f%%"
        ),
        "Pessoas afetadas INCT": st.column_config.NumberColumn(format="%d"),
    },
)

st.download_button(
    "Baixar tabela (CSV)",
    data=tabela.to_csv(index=False).encode("utf-8-sig"),
    file_name="ufrgs_inct_por_bairro_530cm.csv",
    mime="text/csv",
)


# -----------------------------------------------------------------------------
# Limitações e fontes
# -----------------------------------------------------------------------------

st.header("Limitações dos dados", divider="gray")

st.warning(
    f"""
    **Atenção ao interpretar os resultados**

    - A UFRGS mede **área coberta pela água**; o INCT estima **prédios e
      pessoas**. Os percentuais não são diretamente equivalentes.
    - A malha de bairros usada pela UFRGS tem {len(df) + len(sem_par_ufrgs)}
      bairros. Os bairros criados em 2016 não aparecem nela e ficam fora desta
      tela: {", ".join(sem_par_inct)}.
    - A população afetada do INCT é uma estimativa que supõe as pessoas
      distribuídas igualmente entre todos os prédios do bairro.
    - A mancha de 5,3 m é comparada com a simulação a 5,3 m; o recorde de
      maio de 2024 foi 5,35 m.
    """
)

st.caption(
    """
    **Fontes.**
    UFRGS, *Cheias de 2024 na Região Hidrográfica do Guaíba*, arquivo
    `cheias_rhguaiba_2024_db_v12.gpkg`, camadas `poa_inundacao_2024_530cm`,
    `rhguaiba_sentinel2_agua_obs_06052024_validada` e `poa_admin_bairros`.
    Disponível em <https://zenodo.org/records/13227745>. Coletado em 08/11/2026.
    INCT SiMAI, simulação de prédios afetados por nível do Guaíba
    (`data_alterado.json`, após a limpeza da equipe).
    """
)
