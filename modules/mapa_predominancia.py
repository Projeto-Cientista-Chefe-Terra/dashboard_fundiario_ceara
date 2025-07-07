import folium
import streamlit as st
import geopandas as gpd
import pandas as pd
from branca.element import Template, MacroElement
from folium.plugins import HeatMap
from typing import TypedDict
from folium.plugins import MiniMap, Fullscreen

from streamlit_folium import st_folium
from public.cores import CORES 


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

preparar_dados_ctx = st.cache_resource()(preparar_dados)


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



def render_view_predominancia_map(dados_fundiarios,contorno_municipios):
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
        #Adicionando minimap
        MiniMap(toggle_display=True).add_to(mapa_obj)
        Fullscreen().add_to(mapa_obj)
        st_folium(mapa_obj, width=1000, height=600, returned_objects=[])

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
