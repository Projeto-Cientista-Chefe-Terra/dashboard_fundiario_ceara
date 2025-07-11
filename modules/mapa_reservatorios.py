# modules/mapa_reservatorios.py

import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MiniMap, Fullscreen, MarkerCluster
import requests
import math
from typing import Optional
from shapely.geometry import shape
from typing import Dict, List, Any, Optional
import os
import json



# Configurações padrão
CENTRO_CEARA = [-5.2, -39.0]
ZOOM_PADRAO = 8
COR_RESERVATORIO = "#006994"
COR_ASSENTAMENTO = "#e67e22"
COR_MUNICIPIO = "#000000"  # cor da borda


# Configuração ajustável da API
DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://localhost:8000")
REQUEST_TIMEOUT = 30  # segundos

# --- Helpers ---

@st.cache_data(ttl=86400)
def _fetch_from_api(endpoint: str, params: Optional[Dict] = None) -> Any:
    """Helper function com tratamento robusto de erros"""
    try:
        st.session_state.setdefault('api_calls', 0)
        st.session_state.api_calls += 1
        
        response = requests.get(
            f"{DATA_SERVICE_URL}/{endpoint}",
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        
        # Verificação especial para evitar erro com endpoint /version
        if endpoint == "version":
            if response.status_code == 404:
                return {'data_version': '1.0.0-default'}  # Versão padrão
            response.raise_for_status()
            return response.json()
        else:
            response.raise_for_status()
            return response.json()
            
    except requests.exceptions.RequestException as e:
        if endpoint == "version":
            return {'data_version': '1.0.0-fallback'}  # Versão de fallback
        
        # Fallback para dados locais se disponível
        if os.path.exists(f"backup/{endpoint}.json"):
            with open(f"backup/{endpoint}.json") as f:
                return json.load(f)
        st.error(f"Erro ao acessar endpoint {endpoint}: {str(e)}")
        raise
# @st.cache_data(ttl=3600)
# def _get_geojson(endpoint: str, municipio: str = "todos") -> Optional[dict]:

#     base = f"http://localhost:8000/{endpoint}"
#     params = {} if municipio.lower() == "todos" else {"municipio": municipio}
#     try:
#         resp = requests.get(base, params=params, timeout=30)
#         resp.raise_for_status()
#         return resp.json()
#     except requests.exceptions.RequestException as e:
#         st.error(f"Erro ao carregar {endpoint}: {e}")
#         return None

@st.cache_data(ttl=3600)
def carregar_reservatorios(municipio: str = "todos") -> Optional[dict]:
    return _fetch_from_api("geojson_reservatorios", {'municipio': municipio})

@st.cache_data(ttl=3600)
def carregar_assentamentos(municipio: str = "todos") -> Optional[dict]:
    return _fetch_from_api("geojson_assentamentos", {'municipio': municipio})

@st.cache_data(ttl=3600)
def carregar_municipios(municipio: str = "todos") -> Optional[dict]:
    return _fetch_from_api("geojson_muni", {'municipio': municipio})

@st.cache_data(ttl=3600)
def obter_municipios_reservatorios() -> list:
    try:
        resp = requests.get("http://tgdmserver:8000/reservatorios_municipios", timeout=10)
        resp.raise_for_status()
        return resp.json().get("municipios", [])
    except requests.exceptions.RequestException:
        return []

# --- Formatação ---
def formatar_valor(valor):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "Não Disponível"
    if isinstance(valor, str) and valor.strip().lower() in ["", "nan", "none", "null"]:
        return "Não Disponível"
    return valor

# --- Camadas do mapa ---
def criar_mapa_base() -> folium.Map:
    return folium.Map(
        location=CENTRO_CEARA,
        zoom_start=ZOOM_PADRAO,
        tiles="cartodbpositron",
        control_scale=True,
        prefer_canvas=True
    )

def adicionar_camada_reservatorios(mapa: folium.Map, geojson_data: dict):
    if not geojson_data or not geojson_data.get("features"):
        st.warning("Nenhum reservatório pra mostrar 😕")
        return

    nome_fg = (
        f'<span style="display:inline-block;'
        f'width:12px;height:12px;background:{COR_RESERVATORIO};'
        f'margin-right:6px;"></span>Reservatórios'
    )
    fg = folium.FeatureGroup(name=nome_fg, overlay=True)

    # Desenha polígonos simplificados
    folium.GeoJson(
        geojson_data,
        style_function=lambda ft: {
            "fillColor": COR_RESERVATORIO,
            "color": "#000000",
            "weight": 1,
            "fillOpacity": 0.7
        },
        simplify_tolerance=0.0001,
        tooltip=folium.GeoJsonTooltip(
            fields=[
                'id_sagreh','nome','proprietario','gerencia',
                'reg_hidrog','nome_municipio_original','ano_constr','ri',
                'o_barrad','area_ha','capacid_m3'
            ],
            aliases=[
                'ID','Nome','Proprietário','Gerência',
                'Região Hidro','Município','Ano','Rio ou Riacho',
                'Barragem','Área (ha)','Capacidade (m³)'
            ],
            sticky=True
        )
    ).add_to(fg)

    # Cluster de markers para pontos
    cluster = MarkerCluster().add_to(fg)
    for feat in geojson_data['features']:
        props = {k: formatar_valor(v) for k,v in feat['properties'].items()}
        geom = feat['geometry']
        # usa shapely para extrair centróide generico
        centroid = shape(geom).centroid
        lon, lat = centroid.x, centroid.y

        tooltip = (
            f"<b>{props.get('nome','—')}</b><br>"
            f"<b>{props.get('proprietario','—')}</b><br>"
            f"<b>{props.get('gerencia','—')}</b><br>"
            f"<b>{props.get('reg_hidrog','—')}</b><br>"            
            f"Município: {props.get('nome_municipio','—')}<br>"
            f"Ano de Construção: {props.get('ano_constr','—')}<br>"
            f"Rio/Riacho: {props.get('ri','—')}<br>"
            f"Barragem: {props.get('o_barrad','—')}<br>"
            f"Capacidade: {props.get('capacid_m3','—')} m³"
        )
        folium.Marker(
            [lat, lon],
            tooltip=tooltip,
            icon=folium.Icon(prefix='fa', icon='tint', color='blue')
        ).add_to(cluster)

    fg.add_to(mapa)


def adicionar_camada_assentamentos(mapa: folium.Map, geojson_data: dict):
    if not geojson_data or not geojson_data.get("features"):
        return

    nome_fg = (
        f'<span style="display:inline-block;'
        f'width:12px;height:12px;background:{COR_ASSENTAMENTO};'
        f'margin-right:6px;"></span>Assentamentos'
    )
    fg = folium.FeatureGroup(name=nome_fg, overlay=True)

    folium.GeoJson(
        geojson_data,
        style_function=lambda ft: {
            "fillColor": COR_ASSENTAMENTO,
            "color": "#000000",
            "weight": 0.5,
            "fillOpacity": 0.5
        },
        simplify_tolerance=0.001,
        tooltip=folium.GeoJsonTooltip(
            fields=['nome_assentamento','nome_municipio','num_familias','area'],
            aliases=['Nome','Município','Famílias','Área (ha)'],
            sticky=True
        )
    ).add_to(fg)

    fg.add_to(mapa)


def adicionar_camada_municipios(mapa: folium.Map, geojson_data: dict):
    if not geojson_data or not geojson_data.get("features"):
        return

    fg = folium.FeatureGroup(name="Limites Municipais", overlay=True)
    folium.GeoJson(
        geojson_data,
        style_function=lambda ft: {
            "fill": False,
            "color": COR_MUNICIPIO,
            "weight": 1
        },
        simplify_tolerance=0.001,
        tooltip=folium.GeoJsonTooltip(
            fields=['nome_municipio'],
            aliases=['Município:'],
            sticky=True
        )
    ).add_to(fg)
    fg.add_to(mapa)
    
# def adicionar_camada_municipios(mapa: folium.Map, geojson_data: dict):
#     if not geojson_data or not geojson_data.get("features"):
#         return

#     fg = folium.FeatureGroup(name="Limites Municipais", overlay=True)

#     # 1) Desenha os limites
#     folium.GeoJson(
#         geojson_data,
#         style_function=lambda ft: {
#             "fill": False,
#             "color": COR_MUNICIPIO,
#             "weight": 1
#         },
#         simplify_tolerance=0.001,
#         tooltip=folium.GeoJsonTooltip(
#             fields=['nome_municipio'],
#             aliases=['Município:'],
#             sticky=True
#         )
#     ).add_to(fg)

#     # 2) Plota label no centróide de cada polígono
#     for feat in geojson_data['features']:
#         props = feat.get('properties', {})
#         nome = props.get('nome_municipio', '')
#         geom = shape(feat['geometry'])
#         cent = geom.centroid  # pega o ponto central
#         folium.map.Marker(
#             [cent.y, cent.x],
#             icon=folium.DivIcon(
#                 html=f"""
#                     <div style="
#                         font-size: 10px;
#                         font-weight: bold;
#                         color: {COR_MUNICIPIO};
#                         text-shadow: 1px 1px 2px white;
#                     ">
#                         {nome}
#                     </div>
#                 """
#             )
#         ).add_to(fg)

#     fg.add_to(mapa)


def obter_estatisticas_reservatorios(geojson_data: dict):
    if not geojson_data or not geojson_data.get("features"):
        return {"total":0,"cap_total_m³":0,"area_ha":0}
    caps, areas = [], []
    for f in geojson_data['features']:
        try: caps.append(float(f['properties'].get('capacid_m3', 0)))
        except: pass
        try: areas.append(float(f['properties'].get('area_ha', 0)))
        except: pass
    return {
        "total": len(geojson_data['features']),
        "cap_total_m³": sum(caps),
        "area_ha": sum(areas)
    }


def render_view_reservatorios_map():
    muni_list = ["Todos"] + obter_municipios_reservatorios()
    col1, col2 = st.columns([10, 3])

    with col2:
        st.markdown("### Filtros")
        sel = st.selectbox("Município", muni_list, index=0)
        stats = obter_estatisticas_reservatorios(
            carregar_reservatorios(sel if sel != "Todos" else "todos")
        )
        st.metric("Reservatórios", stats["total"])
        st.metric("Capacidade total (m³)", f"{stats['cap_total_m³']:.2f}")
        st.metric("Área total (ha)", f"{stats['area_ha']:.2f}")

    with col1:
        if "geo_muni" not in st.session_state:
            st.session_state.geo_muni = carregar_municipios("todos")
        if "geo_assent" not in st.session_state:
            st.session_state.geo_assent = carregar_assentamentos("todos")

        mapa = criar_mapa_base()
        adicionar_camada_municipios(mapa, st.session_state.geo_muni)
        adicionar_camada_assentamentos(mapa, st.session_state.geo_assent)

        dados_res = carregar_reservatorios(sel if sel != "Todos" else "todos")
        if dados_res and dados_res.get("features"):
            adicionar_camada_reservatorios(mapa, dados_res)
        else:
            st.warning("Nenhum reservatório encontrado para esse filtro.")

        folium.LayerControl(collapsed=False).add_to(mapa)
        MiniMap(toggle_display=True).add_to(mapa)
        Fullscreen().add_to(mapa)
        st_folium(mapa, width=1000, height=800, returned_objects=[])

