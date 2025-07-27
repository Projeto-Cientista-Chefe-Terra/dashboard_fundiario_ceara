import os
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MiniMap,Fullscreen
import requests
from typing import Optional
import math

from modules.mapa_reservatorios import adicionar_camada_municipios, carregar_municipios

DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://localhost:8000")


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
        url = f"{DATA_SERVICE_URL}/geojson_assentamentos?municipio={municipio}&tipo={tipo}&tolerance={tolerancia}"
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
        for campo in campos_minimos:
            if campo not in props:
                props[campo] = "Não Disponível"
            else:
                props[campo] = formatar_valor(props[campo])

    # criando grupo para cada tipo
    grupos = {
        "Federal": folium.FeatureGroup(
            name=f'<span style="display:inline-block;'
            f'width:12px;height:12px;background:{CORES_ASSENTAMENTOS["Federal"]};'
            f'margin-right:6px;"></span>Federal',
            overlay=True,
        ),
        "Estadual": folium.FeatureGroup(
            name=f'<span style="display:inline-block;'
            f'width:12px;height:12px;background:{CORES_ASSENTAMENTOS["Estadual"]};'
            f'margin-right:6px;"></span>Estadual',
            overlay=True,
        ),
    }

    # Adiciona cada feature ao grupo correspondente
    for feature in features:
        tipo = feature['properties'].get('tipo_assentamento', 'Outros').capitalize()
        if tipo not in grupos:
            continue  # Ignora tipos não mapeados

        # Cria um GeoJSON individual para cada feature (simplificado)
        single_feature_geojson = {
            "type": "FeatureCollection",
            "features": [feature]
        }

        # Adiciona ao GeoJson do grupo correspondente
        folium.GeoJson(
            single_feature_geojson,
            style_function=lambda ft, tipo=tipo: {
                'fillColor': CORES_ASSENTAMENTOS.get(tipo, "#ff7f0e"),
                'color': '#000000',
                'weight': 0.5,
                'fillOpacity': 0.7
            },
            tooltip=folium.GeoJsonTooltip(
                fields=campos_minimos,
                aliases=[f"{campo}: " for campo in campos_minimos],
                sticky=True,
                style="font-family: Arial; font-size: 12px;"
            )
        ).add_to(grupos[tipo])

        # Adiciona marcadores (lógica existente, mas direcionada ao mapa principal)
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
            ).add_to(grupos[tipo])
        except (KeyError, IndexError, TypeError) as e:
            print(f"Erro ao processar feature: {e}")

    # Adicionando todos os grupos ao mapa
    for grupo in grupos.values():
        grupo.add_to(mapa)

    # Adiciona minimapa
    MiniMap(toggle_display=True).add_to(mapa)
    Fullscreen().add_to(mapa)
    folium.LayerControl(collapsed=False).add_to(mapa)


def obter_municipios() -> list:
    """Obtém lista de municípios da API"""
    try:
        url = f"{DATA_SERVICE_URL}/assentamentos_municipios"
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
def render_view_assentamento_map():
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
        st.metric("Área total (ha)", str(stats["area_total"]).replace('.', ','))
        
        if municipio_selecionado == 'Todos' and tipo_selecionado == 'Todos':
            st.metric("Área média (ha)", str(stats["area_media"]).replace('.', ','))

    with col1:
        # Cria o mapa base
        if "geo_muni" not in st.session_state:
            st.session_state.geo_muni = carregar_municipios("todos")
        mapa = criar_mapa_base()
        adicionar_camada_municipios(mapa, st.session_state.geo_muni, False)
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
                width=1000,
                height=700,
                returned_objects=[],
                use_container_width=True
            )
        else:
            st.warning("Nenhum dado disponível para os filtros selecionados.")
