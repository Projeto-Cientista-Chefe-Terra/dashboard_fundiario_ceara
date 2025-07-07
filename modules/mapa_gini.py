import streamlit as st
import pandas as pd
import unicodedata
import folium
import numpy as np
from folium.features import GeoJsonTooltip
from shapely.geometry import Polygon, MultiPolygon
from streamlit_folium import st_folium
from folium.plugins import MiniMap, Fullscreen

@st.cache_data
def normalizar_nome(nome):
    if not isinstance(nome, str):
        return nome
    s = unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode()
    return s.lower().replace(" ", "_").upper()

# Cálculo de Gini
@st.cache_data
def gini(_arr):
    a = np.sort(np.array(_arr, dtype=float))
    a = a[a >= 0]
    n = a.size
    if n == 0:
        return float("nan")
    idx = np.arange(1, n + 1)
    return (2 * np.sum(idx * a) / (n * np.sum(a))) - (n + 1) / n


# Prepara DataFrames para cálculos
@st.cache_data
def processar_dataframes(df_props, out_iqr, out_err):
    """Filtra e prepara os dataframes principais"""

    # Cria cópias filtradas
    df_with = df_props.copy()
    df_no = df_props.drop(pd.concat([out_iqr, out_err]).drop_duplicates().index)

    return df_with, df_no

@st.cache_data
def normalizar_df(df):
    """Normaliza apenas DataFrames comuns"""
    df = df.copy()
    df["nome_municipio_original"] = df["nome_municipio"]
    df["nome_municipio"] = df["nome_municipio"].apply(normalizar_nome)
    return df

def normalizar_municipios(municipios):
    """Função sem cache para GeoDataFrame"""
    municipios = municipios.copy()
    municipios["nome_municipio"] = municipios["nome_municipio"].apply(normalizar_nome)
    return municipios.rename(columns={"nome_municipio": "nome_municipio"})


def contar_lotes(df_with, df_no):
    """Conta lotes por município e identifica warnings"""

    for df in [df_with, df_no]:
        df["cnt"] = df.groupby("nome_municipio")["area"].transform("count")

    warning_munis = df_with[df_with["cnt"] < 100]["nome_municipio"].unique().tolist()

    return df_with, df_no, warning_munis


# Geração DataFrame de Gini por município
def calc_gini_df(df):
    return (
        df.groupby("nome_municipio")
        .agg(
            nome_municipio_original=("nome_municipio_original", "first"),
            regiao_administrativa=("regiao_administrativa", "first"),
            cnt=("cnt", "first"),
            gini_area=("area", lambda x: gini(x.values)),
        )
        .reset_index()
    )



# Estilo de polígonos
@st.cache_data
def style_fn(f):
    p = f["properties"]
    if p.get("cnt") == 1:
        return {
            "fillColor": "#FFD700",
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.8,
        }
    g = p.get("gini_area")
    if pd.isna(g):
        return {
            "fillColor": "#D3D3D3",
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.8,
        }
    if g <= 0.700:
        c = "#f9c0ba"
    elif g <= 0.800:
        c = "#d8948c"
    elif g <= 0.850:
        c = "#b66960"
    elif g <= 0.900:
        c = "#923f37"
    else:
        c = "#6e1111"
    return {"fillColor": c, "color": "black", "weight": 0.5, "fillOpacity": 0.8}

# Renderização de mapas
def render_map(tab, geo_df):
    with tab:
        m = folium.Map(
            location=[-5.2, -39.5], zoom_start=8, tiles="cartodbpositron"
        )

        tooltip = GeoJsonTooltip(
            fields=["nome_municipio_original", "gini_area", "cnt"],
            aliases=["Município: ", "Índice de Gini: ", "Imóveis: "],
            localize=True,
            sticky=True,
        )

        folium.GeoJson(geo_df, style_function=style_fn, tooltip=tooltip).add_to(m)
        for _, row in geo_df.iterrows():
            geom = row.geometry
            if isinstance(geom, (Polygon, MultiPolygon)):
                c = geom.centroid
                folium.map.Marker(
                    [c.y, c.x],
                    icon=folium.DivIcon(
                        html=f"""<div style='font-size:6pt; font-weight:bold; color:black; text-shadow:0 0 4px white;'>{row['nome_municipio']}</div>"""
                    ),
                ).add_to(m)
        # Adiciona aviso de Imóveis únicos
        legend_html = """
                <div style='position:fixed;top:10px;right:10px;background:white;padding:10px;border:1px solid grey;font-size:14px;z-index:9999;'>
                <b>Intervalos de Gini</b><br>
                <i style='background:#FFD700;width:12px;height:12px;float:left;margin-right:4px'></i>< 100 imóveis<br>
                <i style='background:#f9c0ba;width:12px;height:12px;float:left;margin-right:4px'></i>≤0.700<br>
                <i style='background:#d8948c;width:12px;height:12px;float:left;margin-right:4px'></i>0.701–0.800<br>
                <i style='background:#b66960;width:12px;height:12px;float:left;margin-right:4px'></i>0.801–0.850<br>
                <i style='background:#923f37;width:12px;height:12px;float:left;margin-right:4px'></i>0.851–0.900<br>
                <i style='background:#6e1111;width:12px;height:12px;float:left;margin-right:4px'></i>>0.900<br>
                <i style='background:#D3D3D3;width:12px;height:12px;float:left;margin-right:4px'></i>Sem dados
                </div>"""
        m.get_root().html.add_child(folium.Element(legend_html))
        #Adicionando minimap
        MiniMap(toggle_display=True).add_to(m)
        Fullscreen().add_to(m)
        st_folium(m, width=1000, height=900, returned_objects=[])

def render_view_gini_map(df_props,municipios):
    # Carrega dados
    # df_props = load_data("")
    # municipios = load_municipios("")


    # Detecta outliers via IQR para uso interno
    areas = df_props["area"]
    Q1, Q3 = areas.quantile([0.25, 0.75])
    IQR = Q3 - Q1
    out_iqr = df_props[(areas < Q1 - 1.5 * IQR) | (areas > Q3 + 1.5 * IQR)]
    # out_err = df_props[df_props['area'] >= HALF_STATE_HA]
    HALF_STATE_HA = 1488860 / 2  # ~744430 ha
    out_err = df_props[
        (df_props["area"] >= HALF_STATE_HA) | (df_props["lote_id"] == 8601)]
    
    df_with, df_no = processar_dataframes(df_props, out_iqr, out_err)
    df_with = normalizar_df(df_with)
    df_no = normalizar_df(df_no)
    muni_geo = normalizar_municipios(municipios)
    df_with, df_no, warning_munis = contar_lotes(df_with, df_no)
    
    gini_with = calc_gini_df(df_with)
    # gini_no = calc_gini_df(df_no)

    # Filtra warnings do DataFrame de tabelas
    gini_with_filt = gini_with[gini_with["cnt"] > 1]
    # gini_no_filt = gini_no[gini_no["cnt"] > 1]

    # Cálculo de Gini estadual sem warnings mas incluindo outliers
    state_no_warn = gini(
        df_with[~df_with["nome_municipio"].isin(warning_munis)]["area"].values
    )

    # Merge GeoJSON + Gini
    geo_with = muni_geo.merge(gini_with, on="nome_municipio", how="left")
    # geo_no = muni_geo.merge(gini_no, on="nome_municipio", how="left")
    
    
    col1, col2 = st.columns([7, 3])

    # Tabelas
    with col2:
        st.subheader("Índice de Gini ")

        circular_grafic = f"""
        <style>
        .grafico {{
            --porcentagem: {state_no_warn:.2f};  # Usando o valor da sua métrica
            --tamanho: 100px;
            
            width: var(--tamanho);
            height: var(--tamanho);
            border-radius: 50%;
            background: conic-gradient(
                #6e1111 0%,
                #f5e1df calc(var(--porcentagem) * 100%),
                #fcf1f0 0%
            );
            display: grid;
            place-items: center;
            margin: 10px auto;
        }}

        .grafico::before {{
            content: "{state_no_warn:.2%}";  # Formata como porcentagem
            display: grid;
            place-items: center;
            width: 70%;
            height: 70%;
            background: white;
            border-radius: 50%;
            color: #0c0906;
        }}
        </style>

        <div class="grafico" data-value="{state_no_warn:.0%}"></div>
        """
        st.markdown(
            circular_grafic,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p style='text-align: center; color:black;'>Valor absoluto {state_no_warn:.4f}</p>",
            unsafe_allow_html=True,
        )
        st.subheader("Gini por município")
        st.dataframe(
            gini_with_filt[
                ["regiao_administrativa", "nome_municipio_original", "cnt", "gini_area"]
            ].rename(
                columns={
                    "regiao_administrativa": "Região",
                    "nome_municipio_original": "Município",
                    "gini_area": "Gini",
                    "cnt": "Quantidade de Imoveis"
                }
            ),
            use_container_width=True,
        )
        
# Renderiza mapas
    render_map(col1, geo_with)

