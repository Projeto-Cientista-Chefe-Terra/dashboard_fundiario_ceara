# modules/mapa_contextual.py

# import folium
# import geopandas as gpd
# import pandas as pd
# from branca.element import Template, MacroElement
# import streamlit as st
# from folium.plugins import HeatMap  # <-- Import do HeatMap


# import geopandas as gpd

# def preparar_dados(
#     df_ctx: pd.DataFrame, ___muni_gdf: gpd.GeoDataFrame
# ) -> gpd.GeoDataFrame:
#     """
#     Agrega contagens por município, calcula dominante e proporção de dominância.
#     """
#     tbl = df_ctx.groupby(["nome_municipio", "categoria"]).size().unstack(fill_value=0)
#     tbl["total"] = tbl.sum(axis=1)
#     tbl["dominante"] = tbl.drop(columns=["total"]).idxmax(axis=1)
#     tbl["prop_dom"] = tbl.apply(
#         lambda row: row[row["dominante"]] / row["total"] if row["total"] > 0 else 0,
#         axis=1,
#     )
#     tbl = tbl.reset_index() # Depois do groupby, "nome_municipio" vira índice. Aqui vira coluna de novo.
#     gdf = ___muni_gdf.merge(tbl, on="nome_municipio", how="left") # ___muni_gdf.merge(tbl, on="nome_municipio", how="left")

#     for col in [
#         "Pequena Propriedade < 1 MF",
#         "Pequena Propriedade",
#         "Média Propriedade",
#         "Grande Propriedade",
#         "total",
#         "prop_dom",
#     ]:
#         gdf[col] = gdf.get(col, 0).fillna(0)
#         gdf["dominante"] = gdf["dominante"].fillna("Sem Registros")

#     print(f"Tamanho do dataframe recebido: {len(df_ctx)} linhas. Tamanho do dataframe enviado: {len(gdf)} linhas.")
#     return gdf.set_geometry("geometry")


# def criar_mapa_contextual(
#     gdf: gpd.GeoDataFrame,
#     modo_mapa: str = "_categorias Dominantes", #Coroplético
#     categoria_heatmap: str = None,
#     cores: dict = None,
#     contorno_municipios: gpd.GeoDataFrame = None
# ) -> folium.Map:
#     if cores is None:
#         cores = {
#             "Pequena Propriedade < 1 MF": "#fecc5c",
#             "Pequena Propriedade": "#fd8d3c",
#             "Média Propriedade": "#f03b20",
#             "Grande Propriedade": "#bd0026",
#             "Sem Registros": "#cccccc",
#         }
#     centro = [-5.4984, -39.3200]
#     mapa = folium.Map(location=centro, zoom_start=7)

#     # Camada base: contorno dos municípios (deixa todos visíveis!)
#     if contorno_municipios is not None:
#         folium.GeoJson(
#             contorno_municipios,
#             style_function=lambda x: {
#                 "fillOpacity": 0,
#                 "color": "#888",
#                 "weight": 3
#             },
#             tooltip=folium.features.GeoJsonTooltip(
#                 fields=["nome_municipio"],
#                 aliases=["Município"]
#             ),
#             name="Limite dos Municípios"
#         ).add_to(mapa)

#     if modo_mapa == "Heatmap" and categoria_heatmap and categoria_heatmap in gdf.columns:
#         # ---------- Heatmap ----------
#         heat_data = []
#         for _, row in gdf.iterrows():
#             if row[categoria_heatmap] > 0 and row.geometry.centroid.is_valid:
#                 lon, lat = row.geometry.centroid.x, row.geometry.centroid.y
#                 heat_data.append([lat, lon, row[categoria_heatmap]])
#         if heat_data:
#             cor_forte = cores.get(categoria_heatmap, "#fd8d3c")
#             gradient = {
#                 0.0: "#ffffff",    # branco no mínimo
#                 1.0: cor_forte     # cor da categoria (cheio)
#             }
#             HeatMap(
#                 heat_data,
#                 min_opacity=0.3,
#                 max_opacity=0.9,
#                 radius=35,
#                 blur=18,
#                 gradient=gradient,
#                 name=f"Heatmap: {categoria_heatmap}"
#             ).add_to(mapa)
#         folium.LayerControl().add_to(mapa)

#         # Legenda
#         legenda = """
#         {% macro html(this, kwargs) %}
#         <div id='legend' style="
#            position: fixed; bottom: 50px; left: 50px;
#            width: 200px; background: white; padding: 10px;
#            border:2px solid grey; z-index:9999;
#            font-size:11px; line-height:1.2em;">
#           <b>_categorias de Lotes</b><br>
#           {% for cat, color in this.cores.items() %}
#             <i style="background:{{color}};width:18px;height:14px;
#                       display:inline-block;margin-right:8px;"></i>{{cat}}<br>
#           {% endfor %}
#         </div>
#         {% endmacro %}
#         """
#         macro = MacroElement()
#         macro._template = Template(legenda)
#         macro.cores = cores
#         mapa.get_root().add_child(macro)
#     else:
#         # ---------- Coroplético (categoria dominante = cor) ----------
#             # Camada base: contorno dos municípios (deixa todos visíveis!)
#         if contorno_municipios is not None:
#             folium.GeoJson(
#                 contorno_municipios,
#                 style_function=lambda x: {
#                     "fillOpacity": 0,
#                     "color": "#888",
#                     "weight": 3
#                 },
#                 tooltip=folium.features.GeoJsonTooltip(
#                     fields=["nome_municipio"],
#                     aliases=["Município"]
#                 ),
#                 name="Limite dos Municípios"
#             ).add_to(mapa)

#         def style(feature):
#             props = feature['properties']
#             cat = props.get('dominante', 'Sem Registros')
#             return {
#                 'fillColor': cores.get(cat, cores['Sem Registros']),
#                 'color': 'black',
#                 'weight': 0.4,
#                 'fillOpacity': 0.8,
#             }
#         folium.GeoJson(
#             gdf,
#             style_function=style,
#             tooltip=folium.features.GeoJsonTooltip(
#                 fields=[
#                     'nome_municipio','total','Pequena Propriedade < 1 MF','Pequena Propriedade',
#                     'Média Propriedade','Grande Propriedade','dominante'
#                 ],
#                 aliases=[
#                     'Município','Total:','Pequena Propriedade < 1 MF:',
#                     'Pequenas Propriedades:','Médias Propriedades:',
#                     'Grandes Propriedades:','Categoria Dominante:'
#                 ],
#                 localize=True,
#                 labels=True,
#                 sticky=False
#             ),
#             name="_categorias Dominantes"
#         ).add_to(mapa)
#         folium.LayerControl().add_to(mapa)

#         # Legenda
#         legenda = """
#         {% macro html(this, kwargs) %}
#         <div id='legend' style="
#            position: fixed; bottom: 50px; left: 50px;
#            width: 220px; background: white; padding: 10px;
#            border:2px solid grey; z-index:9999;
#            font-size:12px; line-height:1.2em;">
#           <b>_categorias de Lotes</b><br>
#           {% for cat, color in this.cores.items() %}
#             <i style="background:{{color}};width:18px;height:14px;
#                       display:inline-block;margin-right:8px;"></i>{{cat}}<br>
#           {% endfor %}
#         </div>
#         {% endmacro %}
#         """
#         macro = MacroElement()
#         macro._template = Template(legenda)
#         macro.cores = cores
#         mapa.get_root().add_child(macro)

#     return mapa

# modules/mapa_contextual.py

import folium
import geopandas as gpd
import pandas as pd
from branca.element import Template, MacroElement
from folium.plugins import HeatMap
from typing import TypedDict

class DebugInfo(TypedDict):
    municipios_recebidos: int
    municipios_com_dados: int | None  # None até ser calculado
    municipios_sem_dados: int | None

def preparar_dados(
    df_ctx: pd.DataFrame,
    _muni_gdf: gpd.GeoDataFrame,
    _categorias: list[str]
) -> tuple[gpd.GeoDataFrame, pd.DataFrame, DebugInfo]:
    """
    Processa dados fundiários e retorna tuple com:
    - GeoDataFrame para visualizações espaciais (mantém todos municípios)
    - DataFrame tabular para análises estatísticas

    Parâmetros:
        df_ctx: DataFrame com dados dos lotes
        _muni_gdf: GeoDataFrame com geometrias dos municípios
        _categorias: Lista de categorias a considerar
    
    Retorno:
        tuple(gdf_geo, df_tabular)
    """

    # Debug: captura info dos municípios recebidos
    debug_info = {
        "municipios_recebidos": len(_muni_gdf),
        "municipios_com_dados": None,
        "municipios_sem_dados": None
    }

   
    # 1. Agregação dos dados brutos
    tbl = (
        df_ctx.groupby(["nome_municipio", "categoria"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=_categorias, fill_value=0)
    )
    
    # 2. Cálculos derivados
    tbl["total"] = tbl.sum(axis=1)
    has_data = tbl["total"] > 0
    tbl["dominante"] = tbl[_categorias].idxmax(axis=1).where(has_data, "Sem Registros")
    tbl["prop_dom"] = (tbl[_categorias].max(axis=1) / tbl["total"]).where(has_data, 0)
    
    # 3. DataFrame tabular completo
    df_tabular = tbl.reset_index()
    
    # 4. Merge espacial (garante todos municípios)
    gdf_geo = _muni_gdf.merge(
        df_tabular,
        on="nome_municipio",
        how="left"
    )
    
    # 5. Tratamento de valores ausentes de forma explícita
    fill_values = {cat: 0 for cat in _categorias}
    fill_values.update({"total": 0, "prop_dom": 0, "dominante": "Sem Registros"})
    
    gdf_geo = gdf_geo.fillna(fill_values)
    
    # Atualiza debug info após processamento
    debug_info.update({
        "municipios_com_dados": int(has_data.sum()),
        "municipios_sem_dados": len(_muni_gdf) - int(has_data.sum())
    })
    
    return gdf_geo.set_geometry("geometry"), df_tabular, debug_info

def criar_mapa_contextual(
    gdf: gpd.GeoDataFrame,
    modo_mapa: str = "_categorias Dominantes",
    categoria_heatmap: str = None,
    cores: dict = None,
    contorno_municipios: gpd.GeoDataFrame = None
) -> folium.Map:
    cores = cores or {
        "Pequena Propriedade < 1 MF": "#fecc5c",
        "Pequena Propriedade": "#fd8d3c",
        "Média Propriedade": "#f03b20",
        "Grande Propriedade": "#bd0026",
        "Sem Registros": "#cccccc",
    }
    
    mapa = folium.Map(location=[-5.4984, -39.3200], zoom_start=7)
    
    # Adiciona contorno dos municípios se fornecido
    if contorno_municipios is not None:
        folium.GeoJson(
            contorno_municipios,
            style_function=lambda x: {"fillOpacity": 0, "color": "#888", "weight": 3},
            tooltip=folium.GeoJsonTooltip(fields=["nome_municipio"], aliases=["Município"]),
            name="Limite dos Municípios"
        ).add_to(mapa)

    if modo_mapa == "Heatmap" and categoria_heatmap in gdf.columns:
        # Configuração do Heatmap
        heat_data = [
            [row.geometry.centroid.y, row.geometry.centroid.x, row[categoria_heatmap]]
            for _, row in gdf.iterrows()
            if row[categoria_heatmap] > 0 and row.geometry.centroid.is_valid
        ]
        
        if heat_data:
            HeatMap(
                heat_data,
                min_opacity=0.3,
                max_opacity=0.9,
                radius=35,
                blur=18,
                gradient={0.0: "#ffffff", 1.0: cores.get(categoria_heatmap, "#fd8d3c")},
                name=f"Heatmap: {categoria_heatmap}"
            ).add_to(mapa)
    else:
        # Mapa Coroplético
        folium.GeoJson(
            gdf,
            style_function=lambda feature: {
                'fillColor': cores.get(feature['properties'].get('dominante'), cores['Sem Registros']),
                'color': 'black',
                'weight': 0.4,
                'fillOpacity': 0.8,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['nome_municipio', 'dominante'],
                aliases=['Município:', 'Tipo Dominante:'],
                # fields=[
                #     'nome_municipio','total','Pequena Propriedade < 1 MF','Pequena Propriedade',
                #     'Média Propriedade','Grande Propriedade','dominante'
                # ],
                # aliases=[
                #     'Município','Total de Lotes','Total de Pequena Propriedade < 1 MF',
                #     'Total de Pequenas Propriedades','Total de Médias Propriedades',
                #     'Total de Grandes Propriedades','Categoria Dominante'
                # ],
                localize=True,
                labels=True,
                sticky=False
            ),
            name="Categorias Dominantes"
        ).add_to(mapa)

    # Adiciona legenda e controles
    _adicionar_legenda(mapa, cores)
    folium.LayerControl().add_to(mapa)
    
    return mapa

def _adicionar_legenda(mapa: folium.Map, cores: dict):
    """Adiciona legenda padronizada ao mapa"""
    legenda = """
    {% macro html(this, kwargs) %}
    <div id='legend' style="
       position: fixed; bottom: 50px; left: 50px;
       width: 220px; background: white; padding: 10px;
       border:2px solid grey; z-index:9999;
       font-size:12px; line-height:1.2em;">
      <b>Classificação dos Lotes</b><br>
      {% for cat, color in this.cores.items() %}
        <i style="background:{{color}};width:18px;height:14px;
                  display:inline-block;margin-right:8px;"></i>{{cat}}<br>
      {% endfor %}
    </div>
    {% endmacro %}
    """
    macro = MacroElement()
    macro._template = Template(legenda)
    macro.cores = cores
    mapa.get_root().add_child(macro)


