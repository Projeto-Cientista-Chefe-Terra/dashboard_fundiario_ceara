import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MiniMap,Fullscreen
import requests
from typing import Optional

# Configuração da página
st.set_page_config(page_title="Assentamentos do Ceará", layout="wide")
st.title("Mapa de Assentamentos do Ceará")

# Estilo CSS personalizado
st.markdown("""
<style>
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
    }
    .stSelectbox>div>div>select {
        min-width: 300px;
    }
</style>
""", unsafe_allow_html=True)

# Cores para diferentes tipos de assentamento
CORES_ASSENTAMENTOS = {
    "Estadual": "#ff7f0e",
    "Federal": "#1f77b4",

}

# Coordenadas padrão do Ceará
CENTRO_CEARA = [-5.2, -39.0]
ZOOM_PADRAO = 8

# Carga dos dados para o Mapa de Assentamentos

# Controle de simplificação
tolerancia = 0.001


def carregar_geojson(municipio: str = "todos", tolerancia: float = 0.001) -> Optional[dict]:
    """Carrega dados GeoJSON da API"""
    try:
        url = f"http://localhost:8000/geojson_assentamentos?municipio={municipio}&tolerance={tolerancia}"
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

def adicionar_camadas(mapa: folium.Map, geojson_data: dict):
    """Adiciona camadas GeoJSON ao mapa com marcadores nos assentamentos"""
    if not geojson_data or not geojson_data.get("features"):
        st.warning("Nenhum dado de assentamento para exibir.")
        return
    
    # Função de estilo para os polígonos
    style_function = lambda feature: {
        'fillColor': CORES_ASSENTAMENTOS.get(
            feature['properties'].get('_assentamento', 'Outros'),
            "#ff7f0e"  # Cor padrão
        ),
        'color': '#000000',
        'weight': 0.5,
        'fillOpacity': 0.7
    }
    
    # Camada de assentamentos (polígonos)
    folium.GeoJson(
        geojson_data,
        name="Assentamentos",
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=['nome_assentamento', 'nome_municipio_original', 'area','perimetro','tipo_assentamento'],
            aliases=['Assentamento:', 'Município:', 'Área (ha):', 'Perímetro (km):', 'Tipo:'],
            sticky=True,
            style="font-family: Arial; font-size: 12px;"
        ),
        highlight_function=lambda feature: {
            'fillOpacity': 0.9,
            'weight': 2
        }
    ).add_to(mapa)
    
    # Adiciona marcadores para cada assentamento
    for feature in geojson_data['features']:
        try:
            # Obtém o centro do polígono
            if feature['geometry']['type'] == 'MultiPolygon':
                # Pega o primeiro ponto do primeiro polígono como aproximação do centro
                coordenadas = feature['geometry']['coordinates'][0][0][0]
            else:  # Polygon
                coordenadas = feature['geometry']['coordinates'][0][0]
            
            lat, lon = coordenadas[1], coordenadas[0]
            
            # Cria o marcador
            folium.Marker(
                location=[lat, lon],
                # popup=f"<b>{feature['properties']['nome_assentamento']}</b><br>"
                #       f"<b>Município:</b> {feature['properties']['nome_municipio_original']}<br>"
                #       f"<b>Área:</b> {feature['properties']['area']} ha<br>"
                #       f"<b>Perímetro:</b> {feature['properties']['perimetro']} km<br>"
                #       f"<b>Tipo:</b> {feature['properties']['tipo_assentamento']}",
                tooltip=folium.Tooltip(
                    f"<b>{feature['properties']['nome_assentamento']}</b><br>"
                    f"<b>Município:</b> {feature['properties']['nome_municipio_original']}<br>"
                    f"<b>Área:</b> {feature['properties']['area']} ha<br>"
                    f"<b>Perímetro:</b> {feature['properties']['perimetro']} km<br>"
                    f"<b>Tipo:</b> {feature['properties']['tipo_assentamento']}"
                ),
                icon=folium.Icon(
                    color='green' if feature['properties']['tipo_assentamento'] == 'estadual' else 'orange',
                    icon='home' if feature['properties']['tipo_assentamento'] == 'estadual' else 'info-sign',
                    prefix='fa'  # Usa ícones do Font Awesome
                )
            ).add_to(mapa)
        except (KeyError, IndexError) as e:
            print(f"Erro ao processar feature: {e}")

    # Adiciona controle de camadas
    # folium.LayerControl(position='topright', collapsed=False).add_to(mapa)
    

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

# Carrega dados e adiciona ao mapa

municipios = ["Todos"] + obter_municipios()
municipio_selecionado= "Todos"

geojson_data = carregar_geojson(
    municipio="todos" if municipio_selecionado == "Todos" else municipio_selecionado,
    tolerancia=tolerancia
)
# Estatísticas
num_assentamentos = len(geojson_data.get('features', []))

# Corpo principal
col1, col2 = st.columns([12, 4])

with col1:
    # Cria o mapa base
    mapa = criar_mapa_base()
        
    if geojson_data:
        adicionar_camadas(mapa, geojson_data)
        
        # Exibe o mapa
        st_folium(
            mapa,
            width=1200,
            height=700,
            returned_objects=[]
        )
    else:
        st.warning("Nenhum dado disponível para os filtros selecionados.")

with col2:
    st.markdown(f"### Filtros")

    # Carrega municípios
    municipio_selecionado = st.selectbox(
        "Selecione o município:",
        municipios,
        index=0
    )    
    st.markdown("---")

    st.markdown("### Informações")
    # Resumo estatístico
    areas = [f['properties'].get('area', 0) for f in geojson_data['features']]
    if geojson_data and geojson_data.get("features") and municipio_selecionado == 'Todos': 
        st.metric("Total de assentamentos", len(areas))
        st.metric("Área média (ha)", round(sum(areas)/len(areas), 2))
        st.metric("Área total (ha)", round(sum(areas), 2))
    else:
        st.metric("Total de assentamentos", len(areas))
        st.metric("Área total (ha)", round(sum(areas), 2))
    st.markdown("---")
    for tipo, cor in CORES_ASSENTAMENTOS.items():
        st.markdown(f"<span style='color:{cor}; font-weight:bold'>■</span> {tipo}", unsafe_allow_html=True)