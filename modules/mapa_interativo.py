# app_streamlit_folium.py
import streamlit as st
import folium
import json
import geopandas as gpd

from streamlit_folium import st_folium
from folium.plugins import Fullscreen, MiniMap
from modules.data_loader import (
    fetch_regioes, fetch_municipios,
    fetch_geojson_por_regiao, fetch_geojson_por_municipio,
    fetch_geojson_limites
)

from public.cores import CORES 


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


def render_view_mapa_interativo():
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
                    fields=['imovel','data_criacao_lote', 'numero_incra','numero_lote', 'area','situacao_juridica','regiao_administrativa','nome_municipio_original', 'categoria'],
                    aliases=['Nome:','Data de Criação:','N° Incra:','N° Lote:','Área (ha):','Situação Jurídica:','Região Administrativa:','Município:', 'Categoria:'],
                    localize=True
                )
            ).add_to(fg)
            fg.add_to(m)

        with col1:
            with st.spinner("Gerando mapa..."):
                folium.LayerControl(collapsed=False).add_to(m)
                #Adicionando minimap
                MiniMap(toggle_display=True).add_to(m)
                Fullscreen().add_to(m)
                st_folium(m, width=1200, height=900, returned_objects=[],use_container_width=True)
            
        st.stop()   