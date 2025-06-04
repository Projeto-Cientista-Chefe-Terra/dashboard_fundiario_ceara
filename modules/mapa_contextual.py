# modules/mapa_contextual.py

import folium
import geopandas as gpd
import pandas as pd
from branca.element import Template, MacroElement
import streamlit as st

# Cores de dominância
from public.cores import CORES

cores = CORES
cores["Sem Registro"] = "#9fa2a5"
cores["Sem Dados"] = "#cccccc"


def preparar_dados(
    df_ctx: pd.DataFrame, _muni_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """
    Agrega contagens por município, calcula dominante e proporção de dominância.
    """
    # 1) Conta por município e categoria
    tbl = df_ctx.groupby(["municipio_norm", "categoria"]).size().unstack(fill_value=0)
    # 2) Total e dominante
    tbl["total"] = tbl.sum(axis=1)
    tbl["dominante"] = tbl.drop(columns=["total"]).idxmax(axis=1)
    # 3) Proporção de dominância: contagem do dominante / total
    tbl["prop_dom"] = tbl.apply(
        lambda row: row[row["dominante"]] / row["total"] if row["total"] > 0 else 0,
        axis=1,
    )
    tbl = tbl.reset_index()

    # 4) Mescla com geometria dos municípios
    gdf = _muni_gdf.merge(tbl, on="municipio_norm", how="left")

    # 5) Preenche zeros e dados faltantes
    for col in [
        "Pequena Propriedade < 1 MF",
        "Pequena Propriedade",
        "Média Propriedade",
        "Grande Propriedade",
        "total",
        "prop_dom",
    ]:
        gdf[col] = gdf.get(col, 0).fillna(0)
    gdf["dominante"] = gdf["dominante"].fillna("Sem Dados")

    return gdf.set_geometry("geometry")


def criar_mapa_contextual(gdf: gpd.GeoDataFrame) -> folium.Map:
    centro = [-5.4984, -39.3200]
    mapa = folium.Map(location=centro, zoom_start=7)

    # estilo igual antes...
    def style(feature):
        props = feature['properties']
        cat  = props.get('dominante', 'Sem Dados')
        prop = props.get('prop_dom', 0)
        opa  = 0.3 + 0.7 * prop
        return {
            'fillColor': cores.get(cat, cores['Sem Dados']),
            'color': 'black',
            'weight': 0.4,
            'fillOpacity': opa,
        }

    folium.GeoJson(
        gdf,
        style_function=style,
        tooltip=folium.features.GeoJsonTooltip(
            fields=[
                'nome_municipio','total','Pequena Propriedade < 1 MF','Pequena Propriedade',
                'Média Propriedade','Grande Propriedade','dominante'
            ],
            aliases=[
                'Município','Total de Lotes','Total de Pequena Propriedade < 1 MF',
                'Total de Pequenas Propriedades','Total de Médias Propriedades',
                'Total de Grandes Propriedades','Categoria Dominante'
            ],
            localize=True,
            labels=True,
            sticky=False
        )
    ).add_to(mapa)

    # monta o template da legenda usando Jinja2
    legenda = """
    {% macro html(this, kwargs) %}
    <div id='legend' style="
       position: fixed; bottom: 50px; left: 50px;
       width: 220px; background: white; padding: 10px;
       border:2px solid grey; z-index:9999;
       font-size:12px; line-height:1.2em;">
      <b>Categorias</b><br>
      {% for cat, color in this.cores.items() %}
        <i style="background:{{color}};width:12px;height:12px;
                  display:inline-block;margin-right:5px;"></i>{{cat}}<br>
      {% endfor %}
      <hr style="margin:4px 0;">
      <b>Dominância (%)</b><br>
      {% for frac in [0.0,0.25,0.5,0.75,1.0] %}
        {% set opa = 0.3 + 0.7*frac %}
        <i style="background:black;opacity:{{'%.2f' % opa}};
                  width:20px;height:12px;display:inline-block;
                  margin-right:5px;"></i>{{(frac*100)|int}}%<br>
      {% endfor %}
    </div>
    {% endmacro %}
    """

    macro = MacroElement()
    macro._template = Template(legenda)
    # passa o dicionário de cores para o template
    macro.cores = cores  
    mapa.get_root().add_child(macro)

    return mapa
