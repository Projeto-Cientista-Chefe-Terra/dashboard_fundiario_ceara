# modules/grafico_interativo.py

"""
Funções para gerar os gráficos de classificação:
- filtrar_dados(df_class, scope, entidade)
- classificar_propriedades(df_filtrado)
- plot_barras(resultados, titulo, subtitulo)
- plot_pizza(resultados, titulo, subtitulo)
- compute_stats_df(df_class)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from public.cores import CORES
import streamlit as st



@st.cache_data
def filtrar_dados(df: pd.DataFrame, scope: str, entidade: str = None) -> pd.DataFrame:
    if scope == "Todo o Estado":
        return df
    elif scope == "Municípios":
        return df[df["nome_municipio"] == entidade]
    elif scope == "Regiões Administrativas":
        return df[df["regiao_administrativa"] == entidade]
    else:
        raise ValueError(f"Escopo desconhecido: {scope}")

@st.cache_data
def classificar_propriedades(df: pd.DataFrame):
    mf = df["modulo_fiscal"]
    area = df["area"]
    categorias = np.where(
        area < mf,
        "Pequena Propriedade < 1 MF",
        np.where(
            area <= 4 * mf,
            "Pequena Propriedade",
            np.where(area <= 15 * mf, "Média Propriedade", "Grande Propriedade"),
        ),
    )
    counts = pd.Series(categorias).value_counts().to_dict()
    total = int(sum(counts.values()))
    return counts, total


# Modify the plot_barras function:
@st.cache_data
def plot_barras(resultados, titulo, subtitulo) -> plt.Figure:
    """
    Plota gráfico de barras com os valores e anota os totais acima de cada barra.
    """
    # Map category names to colors
    color_map = {
        "Pequena Propriedade < 1 MF": CORES["Pequena Propriedade < 1 MF"],
        "Pequena Propriedade": CORES["Pequena Propriedade"],
        "Média Propriedade": CORES["Média Propriedade"],
        "Grande Propriedade": CORES["Grande Propriedade"],
    }
    fig, ax = plt.subplots(figsize=(10, 10))

    # Get colors in correct order
    colors = [color_map[cat] for cat in resultados.keys()]

    bars = ax.bar(
        resultados.keys(),
        resultados.values(),
        color=colors,
        edgecolor="black",
        alpha=0.85,
    )
    ax.set_title(f"{titulo}\n{subtitulo}", fontsize=16)
    plt.xlabel("Categoria", fontsize=14)
    plt.ylabel("Número de Propriedades", fontsize=14)
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.xticks(rotation=45, fontsize=12)

    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{int(height)}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
        )
    plt.tight_layout()
    return fig


# Modify the plot_pizza function:
@st.cache_data
def plot_pizza(resultados, titulo, subtitulo) -> plt.Figure:
    """
    Plota gráfico de pizza com percentuais e legenda.
    Esse gráfico é tão gostoso quanto uma fatia de pizza (sem exageros, ok?).
    """
    # Map category names to colors
    color_map = {
        "Pequena Propriedade < 1 MF": CORES["Pequena Propriedade < 1 MF"],
        "Pequena Propriedade": CORES["Pequena Propriedade"],
        "Média Propriedade": CORES["Média Propriedade"],
        "Grande Propriedade": CORES["Grande Propriedade"],
    }
    fig, ax = plt.subplots(figsize=(10, 10))

    # Get colors in correct order
    colors = [color_map[cat] for cat in resultados.keys()]

    # plt.figure(figsize=(10, 10))
    wedges, texts, autotexts = ax.pie(
        list(resultados.values()),
        labels=None,
        autopct="%1.1f%%",
        startangle=90,
        colors=colors,
        pctdistance=0.8,
        textprops={'fontsize': 16},
        
    )
    ax.set_title(f"{titulo}\n{subtitulo}", fontsize=16)
    ax.axis("equal")
    ax.legend(
        wedges,
        resultados.keys(),
        title="Tipos de Propriedade",
        loc="upper right", # center left
        bbox_to_anchor=(1, 0, 0.5, 1),
    )
    plt.tight_layout()
    return fig

@st.cache_data
def compute_stats_df(df: pd.DataFrame) -> pd.DataFrame:
    stats = df["area"].describe()
    stats = stats.rename(
        {
            "count": "Contagem",
            "mean": "Média",
            "std": "Desvio Padrão",
            "min": "Mínimo",
            "25%": "1º Quartil",
            "50%": "Mediana",
            "75%": "3º Quartil",
            "max": "Máximo",
        }
    )
    return (
        stats.to_frame(name="Área (ha)")
        .reset_index()
        .rename(columns={"index": "Estatística"})
    )

def render_view_grafico_interativo(df_class):
    col1, col2 = st.columns([6, 4])
    tab1, tab2 = col1.tabs(["Gráfico de Pizza","Gráfico de Barras"])
    # col2.subheader("").markdown("##### Filtrar por:")
    co2_1, co2_2 = col2.columns([1, 1])
    opcao = co2_1.selectbox(
        "Filtrar por:", 
        ["Todo o Estado", "Municípios", "Regiões Administrativas"],
    )
    entidade = ""
    if opcao != "Todo o Estado":
        col = "nome_municipio" if opcao == "Municípios" else "regiao_administrativa"
        entidade = co2_2.selectbox(f"{opcao}:", sorted(df_class[col].dropna().unique()))

    df_filtrado = filtrar_dados(df_class, opcao, entidade)
    resultados, total = classificar_propriedades(df_filtrado)

    def preencher_tabs():
        fig_pizza = plot_pizza(
            resultados, f"Propriedades - {opcao} - {entidade}", f"Total: {total}"
        )
        fig_barra = plot_barras(
            resultados, f"Propriedades - {opcao} - {entidade}", f"Total: {total}"
        )


        tab1.pyplot(fig_pizza)
        tab2.pyplot(fig_barra)
        

        col2.subheader("").markdown("#### Classificação de Propriedades")
        col2.html(f"""
                  <p id="op-ent"><b>[{opcao}]</b>{entidade} </p>
                  """)
        col2.dataframe(df_tab, use_container_width=True, hide_index=True,)

        col2.subheader("").markdown("#### Estatísticas Gerais")
        col2.dataframe(compute_stats_df(df_class), use_container_width=True, hide_index=True,)


    if resultados:
        st.html("<h5>Dados atualizadoe em 24/02/2025</h5>")
        df_tab = pd.DataFrame(
            list(resultados.items()), columns=["Categoria", "Quantidade"]
        )
        df_tab.loc[len(df_tab)] = ["Total", total]

        # Tabs
        preencher_tabs()

    else:
        st.warning("Nenhum dado disponível para o filtro selecionado.")

