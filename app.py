# app.py

# TODO URGENTE: Fazer a carga uma unica vez e ficar usando os DF/GDFs carregados
# TODO Refatorar este código colocando as funções de tratamento de dados e rederizacao nos modulos
# TODO Padronizar todoas as legendas
# TODO Inserir nos mapas os mini-maps
# TODO Inserir a legenda e a cor de "<100 imoveis" nos mapas contextuais e Gini
# TODO Inserir o "?" Em todos as secoes com explicacoes sobre o que e apresentado
# TODO Unificar os data_loaders e refatorar
# TODO Padronizar todas as tabelas para o estilo da tabela presente no Mapa de Gini


import streamlit as st
import pandas as pd
import numpy as np
from streamlit_folium import st_folium
import geopandas as gpd
import unicodedata
import folium
import json
from folium.plugins import MiniMap, Fullscreen
from datetime import datetime
from folium.features import GeoJsonTooltip
from shapely.geometry import Polygon, MultiPolygon
import requests
from typing import Optional, TypedDict
import math

class DebugInfo(TypedDict):
    municipios_recebidos: int
    municipios_com_dados: int | None  # None até ser calculado
    municipios_sem_dados: int | None


from modules.data_loader_aux import (
    fetch_regioes, fetch_municipios,
    fetch_geojson_por_regiao, fetch_geojson_por_municipio,
    fetch_geojson_limites
)

from modules import (
    load_csv_data as load_data,
    load_municipios,
    validate_data,
    filtrar_dados,
    classificar_propriedades,
    plot_barras,
    plot_pizza,
    compute_stats_df,
    load_municipios,
    preparar_dados,
    criar_mapa_contextual,

)


# Configurações
DATA_SERVICE_URL = st.secrets.get("DATA_SERVICE_URL", "http://localhost:8000")
# MAX_FEATURES = 500  # Limite para features simultâneas

st.set_page_config(
    page_title="Dashboard",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# 🔒 Aplicação de Cache
# -----------------------------

# Cacheia a leitura de CSVs e DataFrames pesados (expira em 1h)
load_data = st.cache_resource(ttl=3600)(
    load_data
)

# Cacheia validações e splits de dados (poupando re-execuções)
validate_data = st.cache_resource()(
    validate_data
)

# Cacheia filtros, classificações e estatísticas
filtrar_dados = st.cache_resource()(filtrar_dados)
classificar_propriedades = st.cache_resource()(classificar_propriedades)
compute_stats_df = st.cache_resource()(
    compute_stats_df
)  

# Cacheia GeoDataFrame de municípios e preparação de contexto
load_municipios = st.cache_resource()(load_municipios)
preparar_dados_ctx = st.cache_resource()(preparar_dados)


# -----------------------------
# 🚀 App Streamlit
# -----------------------------

# ---------------------------------------------------
# 0) Definição de funções de visualizações
# ---------------------------------------------------


CORES = {
    "Pequena Propriedade < 1 MF": "#fecc5c",
    "Pequena Propriedade": "#fd8d3c",
    "Média Propriedade": "#f03b20",
    "Grande Propriedade": "#bd0026",
    "Sem Registros": "#eeeee4",

}

@st.cache_resource
def load_once():
    df_raw = load_data("")
    return validate_data(df_raw)


# Carrega e valida dados


    """
    Carrega e valida dados
      - df_all   : DataFrame completo com dados fundiários de todos os municípios do ceará
      - df_class : DataFrame com a classificação de propriedades de todo o ceará
      - gdf_inter: GeoDataFrame pronto para mapa interativo pois contém as informações de geometria as propriedades
      - df_ctx   : DataFrame para mapa de Predominância
      - counts   : dict de totais e descartados
    """

df_all, df_class, df_inter, df_ctx, counts = load_once()

######################### Gráficos de Tabelas Gerais do Estado #########################

def graficos_e_quadros():
    col1, col2 = st.columns([6, 4])
    tab1, tab2 = col1.tabs(["Gráfico de Pizza","Gráfico de Barras"])
    col2.subheader("").markdown("##### Filtrar por:")
    co2_1, co2_2 = col2.columns([1, 1])
    opcao = co2_1.selectbox(
        "Filtrar por:", 
        ["Todo o Estado", "Municípios", "Regiões Administrativas"],
        label_visibility="hidden"
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
        col2.table(df_tab)

        col2.subheader("").markdown("#### Estatísticas Gerais")
        col2.table(compute_stats_df(df_class))


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




######################### Mapa de Predominância #########################

def mapa_de_Predominância():
    
    # Carrega dados
    dados_fundiarios = load_data("")
    contorno_municipios = load_municipios("")
    categorias = [
        "Pequena Propriedade < 1 MF",
        "Pequena Propriedade",
        "Média Propriedade",
        "Grande Propriedade"
    ]
    
    # Processa dados (agora com verificação embutida)
    geo_data, df_tabular, debug_info = preparar_dados_ctx(
        df_ctx=dados_fundiarios,
        _muni_gdf=contorno_municipios,
        _categorias=categorias
    )
    
    col1, col2 = st.columns([7, 3])

    with col2:
        # Controles do mapa
        modo_mapa = st.radio(
            "Tipo de Mapa:",
            options=["Categorias Dominantes", "Heatmap"],
            index=0
        )
        
        categoria_heatmap = None
        if modo_mapa == "Heatmap":
            categoria_heatmap = st.selectbox("Categoria para Heatmap:", categorias)

        # Seleção do município com dados completos
        st.markdown("#### Classificação do Município")
        municipio_selecionado = st.selectbox(
            "Selecione o município",
            options=geo_data["nome_municipio"].sort_values().unique(),
            format_func=lambda x: f"{x} ({'com dados' if df_tabular[df_tabular['nome_municipio']==x]['total'].iloc[0] > 0 else 'sem dados'})"
        )

        # Tabela de dados do município
        #st.markdown("##### Classificação dos Imóveis")
        dados_muni = df_tabular[df_tabular["nome_municipio"] == municipio_selecionado]
        
        st.dataframe(
            dados_muni[categorias + ["total"]]
            .rename(columns={
                "Pequena Propriedade < 1 MF": "Pequena <1MF",
                "total": "Total"
            })
            .T.rename_axis("Categoria")
            .rename(columns={dados_muni.index[0]: "Quantidade de Imóveis"}),
            use_container_width=True
        )

    with col1:
        # Mapa com dados integrados
        mapa_obj = criar_mapa_contextual(
            gdf=geo_data,
            modo_mapa=modo_mapa,
            categoria_heatmap=categoria_heatmap,
            cores=CORES,
            contorno_municipios=contorno_municipios
        )
        Fullscreen().add_to(mapa_obj)
        st_folium(mapa_obj, width=1200, height=600)

    show_debug_info = False #st.checkbox("Mostrar informações de debug")
   
    # # Debug
    if show_debug_info:
        st.subheader("Informações de Processamento")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Municípios Recebidos", debug_info["municipios_recebidos"])
        col2.metric("Com Dados", debug_info["municipios_com_dados"])
        col3.metric("Sem Dados", debug_info["municipios_sem_dados"])
        
        st.write("---")
        st.subheader("Amostra dos Dados")
        
        tab1, tab2 = st.tabs(["GeoDataFrame", "Dados Tabulares"])
        
        with tab1:
            st.write("5 primeiros municípios:", geo_data[["nome_municipio", "dominante", "total"]].head())
            st.write(f"Total no GeoDataFrame: {len(geo_data)} municípios")
            
        with tab2:
            st.write("5 primeiros registros:", df_tabular.head())
            st.write(f"Total no DataFrame: {len(df_tabular)} registros")
        
        st.write("---")
        st.subheader("Verificação de Integridade")
        st.write(f"GeoDataFrame contém todos municípios? {'✅ Sim' if len(geo_data) == debug_info['municipios_recebidos'] else '❌ Não'}")




######################### Mapa Interativo da Malha Fundiária #########################

#TODO Inserir o nome dos municipipios na cadama de delimitacao dos municipios


def mapa_interativo():
    def simplify_geojson(geojson_data, tolerance=0.001):
        if not geojson_data or not geojson_data.get("features"):
            return geojson_data
        gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
        gdf["geometry"] = gdf["geometry"].simplify(tolerance)
        return json.loads(gdf.to_json())

    def get_map_center(geojson):
        for f in geojson["features"]:
            g = f["geometry"]
            if g["type"] == "Polygon":
                lng, lat = g["coordinates"][0][0]
                return [lat, lng]
            elif g["type"] == "MultiPolygon":
                lng, lat = g["coordinates"][0][0][0]
                return [lat, lng]
        return [-5.2, -39.0]



    regioes = fetch_regioes()
    if not regioes:
        st.error("Erro ao carregar regiões.")
        st.stop()
    
    col1, col2 = st.columns([8,2])

    regiao = col2.selectbox("Região administrativa", regioes)

    municipios = fetch_municipios(regiao)
    municipio = col2.selectbox("Município", ["(toda a região)"] + municipios)




    if col2.button("Gerar Mapa"):
        try:
            if municipio == "(toda a região)":
                geojson_data = fetch_geojson_por_regiao(regiao)
                boundaries = []
                for m in municipios:
                    b = fetch_geojson_limites(m)
                    if b and b.get("features"):
                        boundaries.extend(b["features"])
                boundary_geojson = {"type":"FeatureCollection", "features":boundaries} if boundaries else None
            else:
                geojson_data = fetch_geojson_por_municipio(municipio)
                boundary_geojson = fetch_geojson_limites(municipio)
        except Exception as e:
            st.error(f"Erro ao baixar dados: {e}")
            st.stop()

        if not geojson_data or not geojson_data.get("features"):
            st.warning("Nenhuma geometria encontrada.")
            st.stop()

        geojson_data = simplify_geojson(geojson_data)
        center = get_map_center(geojson_data)

        m = folium.Map(location=center, zoom_start=9, tiles=None, control_scale=True)

        folium.TileLayer(
            # tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            # attr='© OpenStreetMap contributors',
            tiles = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
            attr = '© OpenStreetMap contributors, © CARTO',
            name='OpenpenStreetMap',
            control=False,  # para não aparecer no LayerControl
            overlay=True
        ).add_to(m)


        if boundary_geojson and boundary_geojson.get("features"):
            folium.GeoJson(
                boundary_geojson,
                name='<span><svg width="12" height="12"><rect width="12" height="12" fill="#003366"/></svg> Limites Municipais</span>',
                style_function=lambda x: {
                    'color': '#003366', 'weight': 2, 'opacity': 0.8,
                    'fill': False, 'dashArray': '5, 5'
                },
                tooltip=folium.GeoJsonTooltip(fields=['nome_municipio'], aliases=['Município:'])
            ).add_to(m)

        for categoria, cor in CORES.items():
            feats = [f for f in geojson_data["features"]
                    if f.get("properties", {}).get("categoria", "Sem Classificação") == categoria]
            if not feats:
                continue
            cat_geojson = {"type": "FeatureCollection", "features": feats}
            name_html = (
                f'<span><svg width="12" height="12">'
                f'<circle cx="6" cy="6" r="6" fill="{cor}" /></svg> {categoria}</span>'
            )
            fg = folium.FeatureGroup(name=name_html, overlay=True, control=True)
            folium.GeoJson(
                cat_geojson,
                style_function=lambda x, cor=cor: {
                    'fillColor': cor, 'color': '#000', 'weight': 0.5, 'fillOpacity': 0.6
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['imovel','data_criacao_lote', 'numero_incra','numero_lote', 'area','situacao_juridica','regiao_administrativa','nome_municipio_original', 'distrito', 'localidade', 'categoria'],
                    aliases=['Nome:','Data de Criação:','N° Incra:','N° Lote:','Área (ha):','Situação Jurídica:','Região Administrativa:','Município:', 'Distrito:', 'Localidade:', 'Categoria:'],
                    localize=True
                )
            ).add_to(fg)
            fg.add_to(m)

        with col1:
            with st.spinner("Gerando mapa..."):
                folium.LayerControl(collapsed=False).add_to(m)
                Fullscreen().add_to(m)
                st_folium(m, width=1200, height=900, returned_objects=[])
            
        st.stop()


######################### Mapa de Gini do Estado #########################

#TODO Inserir o nome dos municipios e os limitadores em todos os municipios

def mapa_gini():
    # Normalização de nomes

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

    # Carrega dados

    #df_props, municipios = load_data_gini()
    df_props = load_data("")
    municipios = load_municipios("")


    # Detecta outliers via IQR para uso interno
    areas = df_props["area"]
    Q1, Q3 = areas.quantile([0.25, 0.75])
    IQR = Q3 - Q1
    out_iqr = df_props[(areas < Q1 - 1.5 * IQR) | (areas > Q3 + 1.5 * IQR)]
    # out_err = df_props[df_props['area'] >= HALF_STATE_HA]
    HALF_STATE_HA = 1488860 / 2  # ~744430 ha
    out_err = df_props[
        (df_props["area"] >= HALF_STATE_HA) | (df_props["lote_id"] == 8601)
    ]


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

    
    df_with, df_no = processar_dataframes(df_props, out_iqr, out_err)
    df_with = normalizar_df(df_with)
    df_no = normalizar_df(df_no)
    muni_geo = normalizar_municipios(municipios)
    df_with, df_no, warning_munis = contar_lotes(df_with, df_no)

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

    gini_with = calc_gini_df(df_with)
    gini_no = calc_gini_df(df_no)

    # Filtra warnings do DataFrame de tabelas
    gini_with_filt = gini_with[gini_with["cnt"] > 1]
    gini_no_filt = gini_no[gini_no["cnt"] > 1]

    # Cálculo de Gini estadual sem warnings mas incluindo outliers
    state_no_warn = gini(
        df_with[~df_with["nome_municipio"].isin(warning_munis)]["area"].values
    )

    # Merge GeoJSON + Gini
    geo_with = muni_geo.merge(gini_with, on="nome_municipio", how="left")
    geo_no = muni_geo.merge(gini_no, on="nome_municipio", how="left")

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

    col1, col2 = st.columns([7, 3])

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
            Fullscreen().add_to(m)
            st_folium(m, width=1000, height=900)
    # Renderiza mapas
    render_map(col1, geo_with)
    # Tabelas
    with col2:
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

######################### Mapa de Assentamentos do Estado ######################

def mapa_Assentamentos():
 
    CORES_ASSENTAMENTOS = {
        "Estadual": "#ff7f0e",  # Laranja
        "Federal": "#1f77b4",   # Azul
    }
    # Cores para ícones dos marcadores
    CORES_MARKERS = {
        "Estadual": "#ff7f0e",  # Laranja
        "Federal": "#1f77b4",   # Azul
    }
    # Coordenadas padrão do Ceará
    CENTRO_CEARA = [-5.2, -39.0]
    ZOOM_PADRAO = 8

    # Carga dos dados para o Mapa de Assentamentos

    # Controle de simplificação
    tolerancia = 0.001

    def formatar_valor(valor):
        """Substitui valores inválidos por 'Não Disponível'"""
        if valor is None:
            return "Não Disponível"
        if isinstance(valor, float) and math.isnan(valor):
            return "Não Disponível"
        if isinstance(valor, str):
            if valor.strip() == "":
                return "Não Disponível"
            if valor.lower() in ["nan", "none", "null"]:
                return "Não Disponível"
        return valor

    def carregar_geojson(municipio: str = "todos", tipo: str = "todos", tolerancia: float = 0.001) -> Optional[dict]:
        """Carrega dados GeoJSON da API com filtros"""
        try:
            url = f"http://localhost:8000/geojson_assentamentos?municipio={municipio}&tipo={tipo}&tolerance={tolerancia}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Erro ao carregar dados: {str(e)}")
            return None

    def criar_mapa_base() -> folium.Map:
        """Cria um mapa Folium base com configurações padrão"""
        return folium.Map(
            location=CENTRO_CEARA,
            zoom_start=ZOOM_PADRAO,
            tiles="cartodbpositron",
            control_scale=True,
            prefer_canvas=True
        )

    def adicionar_camadas(mapa: folium.Map, geojson_data: dict, tipo_filtrado: str = "todos"):
        if not geojson_data or not geojson_data.get("features"):
            st.warning("Nenhum dado de assentamento para exibir.")
            return
        
        # Filtra features pelo tipo selecionado (se não for "todos")
        features = geojson_data['features']
        if tipo_filtrado != "todos":
            features = [f for f in features if f['properties'].get('tipo_assentamento', '').lower() == tipo_filtrado.lower()]
        
        # Pré-processa as features para formatar os valores e garantir campos mínimos
        campos_minimos = [
            'cd_sipra', 'tipo_assentamento', 'nome_assentamento', 
            'nome_municipio_original', 'num_familias', 'forma_obtecao', 
            'area', 'perimetro'
        ]
        
        for feature in features:
            props = feature['properties']
            
            # Garante que todos os campos mínimos existam
            for campo in campos_minimos:
                if campo not in props:
                    props[campo] = "Não Disponível"
                else:
                    props[campo] = formatar_valor(props[campo])
        
        # Cria um novo GeoJSON apenas com as features filtradas
        filtered_geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        # Verifique os campos disponíveis na primeira feature
        if features:
            available_fields = list(features[0]['properties'].keys())
        else:
            available_fields = []
        
        # Defina os campos a serem usados com fallback
        tooltip_fields = campos_minimos
        
        # Filtre apenas campos disponíveis
        fields_to_use = [f for f in tooltip_fields if f in available_fields]
        
        # Crie aliases correspondentes
        aliases_map = {
            'cd_sipra': 'Cd_SIPRA: ',
            'tipo_assentamento': 'Tipo: ',
            'nome_assentamento': 'Assentamento: ',
            'nome_municipio_original': 'Município: ',
            'num_familias': 'Famílias: ',
            'forma_obtecao': 'Forma de Obtenção: ',
            'area': 'Área (ha): ',
            'perimetro': 'Perímetro (km): '
        }
        aliases_to_use = [aliases_map.get(f, f) for f in fields_to_use]

        # Camada GeoJSON com tooltip adaptável
        folium.GeoJson(
            filtered_geojson,
            name="Assentamentos",
            style_function=lambda feature: {
                'fillColor': CORES_ASSENTAMENTOS.get(
                    feature['properties'].get('tipo_assentamento', 'Outros').capitalize(),
                    "#ff7f0e"  # Cor padrão
                ),
                'color': '#000000',
                'weight': 0.5,
                'fillOpacity': 0.7
            },
            tooltip=folium.GeoJsonTooltip(
                fields=fields_to_use,
                aliases=aliases_to_use,
                sticky=True,
                style="font-family: Arial; font-size: 12px;"
            )
        ).add_to(mapa)
        
        # Adiciona marcadores com tratamento de campos ausentes
        for feature in features:
            try:
                props = feature['properties']
                
                # Obter coordenadas com fallback
                try:
                    if feature['geometry']['type'] == 'MultiPolygon':
                        coords = feature['geometry']['coordinates'][0][0][0]
                        lon, lat = coords[0], coords[1]
                    elif feature['geometry']['type'] == 'Polygon':
                        coords = feature['geometry']['coordinates'][0][0]
                        lon, lat = coords[0], coords[1]
                    else:
                        coords = feature['geometry']['coordinates'][0]
                        lon, lat = coords[0], coords[1]
                except (IndexError, TypeError):
                    lat, lon = CENTRO_CEARA
                
                # Tooltip com valores formatados
                tooltip_content = f"""
                    <b>CD_SIPRA:</b> {props.get('cd_sipra', 'Não Disponível')}<br>
                    <b>Tipo:</b> {props.get('tipo_assentamento', 'Não Disponível')}<br>
                    <b>Assentamento:</b> {props.get('nome_assentamento', 'Não Disponível')}<br>
                    <b>Município:</b> {props.get('nome_municipio_original', 'Não Disponível')}<br>
                    <b>Famílias:</b> {props.get('num_familias', 'Não Disponível')}<br>
                    <b>Forma de Obtenção:</b> {props.get('forma_obtecao', 'Não Disponível')}<br>
                    <b>Área:</b> {props.get('area', 'Não Disponível')} ha<br>
                    <b>Perímetro:</b> {props.get('perimetro', 'Não Disponível')} km<br>
                """
                
                # Determina a cor do marcador baseada no tipo de assentamento
                tipo = props.get('tipo_assentamento', '').capitalize()
                cor_marker = CORES_MARKERS.get(tipo, "#ff7f0e")  # Default laranja
                
                # Cria marcador com ícone personalizado
                folium.Marker(
                    location=[lat, lon],
                    tooltip=folium.Tooltip(tooltip_content),
                    icon=folium.Icon(
                        color='white',
                        icon_color=cor_marker,
                        icon='home',
                        prefix='fa'
                    )
                ).add_to(mapa)
            except (KeyError, IndexError, TypeError) as e:
                print(f"Erro ao processar feature: {e}")

        # Adiciona minimapa
        MiniMap(toggle_display=True).add_to(mapa)
        Fullscreen().add_to(mapa)

    def obter_municipios() -> list:
        """Obtém lista de municípios da API"""
        try:
            url = "http://localhost:8000/assentamentos_municipios"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json().get("municipios", [])
        except requests.exceptions.RequestException:
            return []

    def obter_estatisticas(geojson_data: dict, tipo_filtrado: str = "todos"):
        """Calcula estatísticas com base nos dados filtrados"""
        if not geojson_data or not geojson_data.get("features"):
            return {
                "total_assentamentos": 0,
                "area_total": 0,
                "area_media": 0
            }
        
        features = geojson_data['features']
        
        # Aplica filtro de tipo se necessário
        if tipo_filtrado != "todos":
            features = [f for f in features if f['properties'].get('tipo_assentamento', '').lower() == tipo_filtrado.lower()]
        
        areas = []
        for f in features:
            area = f['properties'].get('area')
            # Ignora valores não numéricos ou inválidos
            if area is not None and area != "Não Disponível":
                try:
                    area_val = float(area)
                    if not math.isnan(area_val):
                        areas.append(area_val)
                except (ValueError, TypeError):
                    pass
        
        num_assentamentos = len(features)
        
        return {
            "total_assentamentos": num_assentamentos,
            "area_total": round(sum(areas), 2) if areas else 0,
            "area_media": round(sum(areas)/len(areas), 2) if areas else 0
        }

    # Carrega dados e adiciona ao mapa
    municipios = ["Todos"] + obter_municipios()
    tipos_assentamento = ["Todos", "Estadual", "Federal"]

    # Corpo principal
    col1, col2 = st.columns([12, 4])

    with col2:
        st.markdown(f"### Filtros")

        # Filtro por município
        municipio_selecionado = st.selectbox(
            "Selecione o município:",
            municipios,
            index=0
        )

        # Filtro por tipo de assentamento
        tipo_selecionado = st.selectbox(
            "Selecione o tipo de assentamento:",
            tipos_assentamento,
            index=0
        )
        
        st.markdown("---")
        st.markdown("### Informações")
        
        # Carrega os dados com base nos filtros selecionados
        geojson_data = carregar_geojson(
            municipio="todos" if municipio_selecionado == "Todos" else municipio_selecionado,
            tipo="todos",  # Carregamos todos os tipos e filtramos depois
            tolerancia=tolerancia
        )

        # Obtém estatísticas com os filtros aplicados
        stats = obter_estatisticas(geojson_data, tipo_selecionado.lower() if tipo_selecionado != "Todos" else "todos")
        
        # Exibe métricas
        st.metric("Total de assentamentos", stats["total_assentamentos"])
        st.metric("Área total (ha)", stats["area_total"])
        
        if municipio_selecionado == 'Todos' and tipo_selecionado == 'Todos':
            st.metric("Área média (ha)", stats["area_media"])

        st.markdown("---")
        for tipo, cor in CORES_ASSENTAMENTOS.items():
            st.markdown(f"<span style='color:{cor}; font-weight:bold'>■</span> {tipo}", unsafe_allow_html=True)

    with col1:
        # Cria o mapa base
        mapa = criar_mapa_base()
            
        if geojson_data:
            # Aplica os filtros no momento de exibição
            adicionar_camadas(
                mapa, 
                geojson_data, 
                tipo_filtrado=tipo_selecionado.lower() if tipo_selecionado != "Todos" else "todos"
            )
            
            # Exibe o mapa
            st_folium(
                mapa,
                width=1200,
                height=700,
                returned_objects=[]
            )
        else:
            st.warning("Nenhum dado disponível para os filtros selecionados.")     
            
            

######################### Mapa de Hidrográfico do Estado #######################

def mapa_hidrográfico():
    centro = [-5.4984, -39.3200]
    mapa = folium.Map(location=centro, zoom_start=7)
    map_container = st.empty()
    st.session_state.mapa_obj = mapa

    # Camada 3 - Exibição
    with map_container:
        st_folium(
            st.session_state.mapa_obj,
            key=f"ctx_map_v",
            width=900,
            height=600,
            returned_objects=["last_clicked"],  # Só retorna o necessário
        )



######################### Estrutura Geral de Navegação #########################



def sobre():
    st.markdown(
        """
    Aplicação de painéis contendo dados estatísticos e geoespaciais da malha fundiária cearense desenvolvido, principalmente, a partir dos dados cadastrados no Instituto de Desenvolvimento Agrário do Ceará (IDACE). Este software faz parte das ações realizadas no âmbito do projeto **Cientista Chefe Terra  de Governança Fundiária e Ambiental**, parceria entre o IDACE, a Universidade Federal do Ceará (UFC) e a Fundação Cearense de Apoio ao Desenvolvimento Científico e Tecnológico (Funcap).
    """
    )

    # Coordenadora Geral
    st.subheader("Coordenadora Geral")
    st.markdown(
        """    
    Profa. Maria Inês Escobar da Costa (EcoEco-UFC)
    """
    )

    # Equipe de Desenvolvimento
    st.subheader("Equipe de Desenvolvimento")
    st.markdown(
        """
    Nossa equipe é composta por:
    - Prof. Wellington Wagner Ferreira Sarmento (SMD-UFC)
    - Me. Patrícia de Sousa Paula (Doutoranda MDCC-UFC)
    - André Lucas de Oliveira Domingues (SMD-UFC)
    - Wesley Barbosa Martins Ribeiro (SMD-UFC)
    """
    )

    # Licença de Uso
    st.subheader("Licença de Uso")
    st.markdown(
        """
    [GNU General Public License (GPL)](https://github.com/Projeto-Cientista-Chefe-Terra/dashboard_fundiario_ceara/blob/main/LICENSE)
    """
    )

    # Link para o projeto
    st.header("Cientista Chefe Terra de Governança Fundiária e Ambiental")
    st.markdown("#### Site Institucional")
    st.markdown("https://ccterra-site.vercel.app")
    st.markdown("#### Código Fonte")
    st.markdown("https://github.com/Projeto-Cientista-Chefe-Terra")

    st.header("Apoio")
    col1, col2, col3, col4 = st.columns(4, vertical_alignment='center')

    with col1:
        st.image("./assets/Idace.png", width=150)
        
    with col2:
        st.image("./assets/CC_Terra.png", width=150)

    with col3:
        st.image("./assets/funcap.png", width=150)
        
    with col4:
        st.image("./assets/ufc_logo.png", width=150)
        



# ---------------------------------------------------
# 1) set_page_config deve ser o primeiro comando do Streamlit
# ---------------------------------------------------


with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown(
    "# Malha Fundiária do Ceará",
    unsafe_allow_html=True,
)


if "current_page" not in st.session_state:
    st.session_state.current_page = "Gráficos"

with st.sidebar:
    st.header("")  # TODO fazer o background diferente para o selecionado
    # CSS para ícones Font Awesome
    if st.button(
        "Gráficos e Quadros", use_container_width=True, icon=":material/bar_chart:"
    ):
        st.session_state.current_page = "Gráficos"
    if st.button(
        "Mapa de Predominância", use_container_width=True, icon=":material/location_on:"
    ):
        st.session_state.current_page = "Mapa de Predominância"
    if st.button("Mapa Interativo", use_container_width=True, icon=":material/map:"):
        st.session_state.current_page = "Mapa Interativo"

    if st.button("Mapa Gini", use_container_width=True, icon=":material/crisis_alert:"):
        st.session_state.current_page = "Mapa Gini"
     
    if st.button("Mapa de Assentamentos", use_container_width=True, icon=":material/globe_location_pin:"):
        st.session_state.current_page = "Mapa de Assentamento"
    
    if st.button("Mapa Hidrográfico", use_container_width=True, icon=":material/water_drop:"):
        st.session_state.current_page = "Mapa Hidrografico"

    if st.button("Sobre", use_container_width=True, icon=":material/info:"):
        st.session_state.current_page = "Sobre"


# ---------------------------------------------------
# 6) Navegação
# ---------------------------------------------------


st.logo("./assets/Idace.png", size="medium")
# ---------------------------------------------------
# 7) Lógica de cada aba
# ---------------------------------------------------
if st.session_state.current_page == "Gráficos":
    st.title("").markdown("### Gráficos e Quadros")
    graficos_e_quadros()

elif st.session_state.current_page == "Mapa de Predominância":
    st.title("").markdown("### Mapa de Predominância do Tipo de  Imóvel por Município")
    mapa_de_Predominância()

elif st.session_state.current_page == "Mapa Interativo":
    st.title("").markdown("### Mapa Interativo")
    mapa_interativo()

elif st.session_state.current_page == "Mapa Gini":
    st.title("").markdown("### Mapa Gini do Ceará")
    mapa_gini()

elif st.session_state.current_page == "Mapa Hidrografico":
    st.title("").markdown("### Mapa Hidrográfico (em desenvolvimento)")
    mapa_hidrográfico()
elif st.session_state.current_page == "Mapa de Assentamento":
    st.title("").markdown("### Mapa de Assentamentos")
    mapa_Assentamentos()

elif st.session_state.current_page == "Sobre":
    st.title("").markdown("### Sobre")
    sobre()
