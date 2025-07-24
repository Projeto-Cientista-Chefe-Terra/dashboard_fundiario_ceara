# import streamlit as st
# import pandas as pd
# import unicodedata
# import folium
# import numpy as np
# from folium.features import GeoJsonTooltip
# from shapely.geometry import Polygon, MultiPolygon
# from streamlit_folium import st_folium
# from folium.plugins import MiniMap, Fullscreen


# @st.cache_data
# def normalizar_nome(nome):
#     if not isinstance(nome, str):
#         return nome
#     s = unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode()
#     return s.lower().replace(" ", "_").upper()


# # Cálculo de Gini
# @st.cache_data
# def gini(_arr):
#     a = np.sort(np.array(_arr, dtype=float))
#     a = a[a >= 0]
#     n = a.size
#     if n == 0:
#         return float("nan")
#     idx = np.arange(1, n + 1)
#     return (2 * np.sum(idx * a) / (n * np.sum(a))) - (n + 1) / n


# # Prepara DataFrames para cálculos
# @st.cache_data
# def processar_dataframes(df_props, out_iqr, out_err):
#     """Filtra e prepara os dataframes principais"""

#     # Cria cópias filtradas
#     df_with = df_props.copy()
#     df_no = df_props.drop(pd.concat([out_iqr, out_err]).drop_duplicates().index)

#     return df_with, df_no


# @st.cache_data
# def normalizar_df(df):
#     """Normaliza apenas DataFrames comuns"""
#     df = df.copy()
#     df["nome_municipio_original"] = df["nome_municipio"]
#     df["nome_municipio"] = df["nome_municipio"].apply(normalizar_nome)
#     return df


# def normalizar_municipios(municipios):
#     """Função sem cache para GeoDataFrame"""
#     municipios = municipios.copy()
#     municipios["nome_municipio"] = municipios["nome_municipio"].apply(normalizar_nome)
#     return municipios.rename(columns={"nome_municipio": "nome_municipio"})


# def contar_lotes(df_with, df_no):
#     """Conta lotes por município e identifica warnings"""

#     for df in [df_with, df_no]:
#         df["cnt"] = df.groupby("nome_municipio")["area"].transform("count")

#     warning_munis = df_with[df_with["cnt"] < 100]["nome_municipio"].unique().tolist()

#     return df_with, df_no, warning_munis


# # Geração DataFrame de Gini por município
# def calc_gini_df(df):
#     return (
#         df.groupby("nome_municipio")
#         .agg(
#             nome_municipio_original=("nome_municipio_original", "first"),
#             regiao_administrativa=("regiao_administrativa", "first"),
#             cnt=("cnt", "first"),
#             gini_area=("area", lambda x: gini(x.values)),
#         )
#         .reset_index()
#     )


# # Estilo de polígonos
# @st.cache_data
# def style_fn(f):
#     p = f["properties"]
#     if p.get("cnt") == 1:
#         return {
#             "fillColor": "#FFD700",
#             "color": "black",
#             "weight": 0.5,
#             "fillOpacity": 0.8,
#         }
#     g = p.get("gini_area")
#     if pd.isna(g):
#         return {
#             "fillColor": "#D3D3D3",
#             "color": "black",
#             "weight": 0.5,
#             "fillOpacity": 0.8,
#         }
#     if g <= 0.700:
#         c = "#f9c0ba"
#     elif g <= 0.800:
#         c = "#d8948c"
#     elif g <= 0.850:
#         c = "#b66960"
#     elif g <= 0.900:
#         c = "#923f37"
#     else:
#         c = "#6e1111"
#     return {"fillColor": c, "color": "black", "weight": 0.5, "fillOpacity": 0.8}


# # Renderização de mapas
# def render_map(tab, geo_df):
#     with tab:
#         m = folium.Map(location=[-5.2, -39.5], zoom_start=8, tiles="cartodbpositron")

#         tooltip = GeoJsonTooltip(
#             fields=["nome_municipio_original", "gini_area", "cnt"],
#             aliases=["Município: ", "Índice de Gini: ", "Imóveis: "],
#             localize=True,
#             sticky=True,
#         )
#         # m.add_child(folium.ClickForLatLng(format_str='"Latitude: " + lat + ", Longitude: " + lng',alert=True  ))
#         folium.GeoJson(geo_df, style_function=style_fn, tooltip=tooltip).add_to(m)
#         for _, row in geo_df.iterrows():
#             geom = row.geometry
#             if isinstance(geom, (Polygon, MultiPolygon)):
#                 c = geom.centroid
#                 folium.map.Marker(
#                     [c.y, c.x],
#                     icon=folium.DivIcon(
#                         html=f"""<div style='font-size:6pt; font-weight:bold; color:black; text-shadow:0 0 4px white;'>{row['nome_municipio']}</div>"""
#                     ),
#                 ).add_to(m)
#         # Adiciona aviso de Imóveis únicos
#         legend_html = """
#                 <div style='position:fixed;top:10px;right:10px;background:white;padding:10px;border:1px solid grey;font-size:14px;z-index:9999;'>
#                 <b>Intervalos de Gini</b><br>
#                 <i style='background:#FFD700;width:12px;height:12px;float:left;margin-right:4px'></i>< 100 imóveis<br>
#                 <i style='background:#f9c0ba;width:12px;height:12px;float:left;margin-right:4px'></i>≤0.700<br>
#                 <i style='background:#d8948c;width:12px;height:12px;float:left;margin-right:4px'></i>0.701–0.800<br>
#                 <i style='background:#b66960;width:12px;height:12px;float:left;margin-right:4px'></i>0.801–0.850<br>
#                 <i style='background:#923f37;width:12px;height:12px;float:left;margin-right:4px'></i>0.851–0.900<br>
#                 <i style='background:#6e1111;width:12px;height:12px;float:left;margin-right:4px'></i>>0.900<br>
#                 <i style='background:#D3D3D3;width:12px;height:12px;float:left;margin-right:4px'></i>Sem dados
#                 </div>"""
#         m.get_root().html.add_child(folium.Element(legend_html))
#         # Adicionando minimap
#         MiniMap(toggle_display=True).add_to(m)
#         Fullscreen().add_to(m)
#         st_folium(
#             m, width=1200, height=900, returned_objects=[], use_container_width=True
#         )


# def render_view_gini_map(df_props, municipios):
#     # Carrega dados
#     # df_props = load_data("")
#     # municipios = load_municipios("")

#     # Detecta outliers via IQR para uso interno
#     areas = df_props["area"]
#     Q1, Q3 = areas.quantile([0.25, 0.75])
#     IQR = Q3 - Q1
#     out_iqr = df_props[(areas < Q1 - 1.5 * IQR) | (areas > Q3 + 1.5 * IQR)]
#     # out_err = df_props[df_props['area'] >= HALF_STATE_HA]
#     HALF_STATE_HA = 1488860 / 2  # ~744430 ha
#     out_err = df_props[
#         (df_props["area"] >= HALF_STATE_HA) | (df_props["lote_id"] == 8601)
#     ]

#     df_with, df_no = processar_dataframes(df_props, out_iqr, out_err)
#     df_with = normalizar_df(df_with)
#     df_no = normalizar_df(df_no)
#     muni_geo = normalizar_municipios(municipios)
#     df_with, df_no, warning_munis = contar_lotes(df_with, df_no)

#     gini_with = calc_gini_df(df_with)
#     # gini_no = calc_gini_df(df_no)

#     # Filtra warnings do DataFrame de tabelas
#     gini_with_filt = gini_with[gini_with["cnt"] > 1]
#     # gini_no_filt = gini_no[gini_no["cnt"] > 1]

#     # Cálculo de Gini estadual sem warnings mas incluindo outliers
#     state_no_warn = gini(
#         df_with[~df_with["nome_municipio"].isin(warning_munis)]["area"].values
#     )

#     # Merge GeoJSON + Gini
#     geo_with = muni_geo.merge(gini_with, on="nome_municipio", how="left")
#     # geo_no = muni_geo.merge(gini_no, on="nome_municipio", how="left")

#     state_no_warn_no_dot = str(state_no_warn).replace(".", ",")
#     col1, col2 = st.columns([7, 3])

#     # Tabelas
#     with col2:
#         st.subheader("Índice de Gini ")

#         circular_grafic = (
#             f"""
#         <style>
#         .grafico {{
#             --porcentagem: {state_no_warn:.2f};  # Usando o valor da sua métrica
#             --tamanho: 100px;
            
#             width: var(--tamanho);
#             height: var(--tamanho);
#             border-radius: 50%;
#             background: conic-gradient(
#                 #6e1111 0%,
#                 #f5e1df calc(var(--porcentagem) * 100%),
#                 #fcf1f0 0%
#             );
#             display: grid;
#             place-items: center;
#             margin: 10px auto;
#         }}

#         .grafico::before {{
#             """
#             + f"""
#             content: "{state_no_warn:.2%}";  # Formata como porcentagem
#             """.replace(
#                 ".", ","
#             )
#             + """
#             display: grid;
#             place-items: center;
#             width: 70%;
#             height: 70%;
#             background: white;
#             border-radius: 50%;
#             color: #0c0906;
#         }}
#         </style>

#         <div class="grafico" data-value="{state_no_warn:.0%}"></div>
#         """
#         )
#         st.markdown(
#             circular_grafic,
#             unsafe_allow_html=True,
#         )
#         st.markdown(
#             f"<p style='text-align: center; color:black;'>Valor absoluto {state_no_warn:.4f}</p>".replace(
#                 ".", ","
#             ),
#             unsafe_allow_html=True,
#         )
#         st.subheader("Gini por município")
#         st.dataframe(
#             gini_with_filt[
#                 ["regiao_administrativa", "nome_municipio_original", "cnt", "gini_area"]
#             ].rename(
#                 columns={
#                     "regiao_administrativa": "Região",
#                     "nome_municipio_original": "Município",
#                     "gini_area": "Gini",
#                     "cnt": "Quantidade de Imoveis",
#                 }
#             ),
#             use_container_width=True,
#             hide_index=True,
#         )

#     # Renderiza mapas
#     render_map(col1, geo_with)


import streamlit as st
import pandas as pd
import folium
import numpy as np
from folium.features import GeoJsonTooltip
from shapely.geometry import Polygon, MultiPolygon
from streamlit_folium import st_folium
from folium.plugins import MiniMap, Fullscreen

# Cálculo de Gini (fórmula clássica)
def gini(arr):
    a = np.array(arr, dtype=float)
    a = a[~np.isnan(a)]  # remove NaNs
    a = a[a > 0]         # remove zeros e negativos
    a = np.sort(a)
    n = a.size
    if n == 0:
        return float("nan")
    total = a.sum()
    if total == 0:
        return float("nan")
    idx = np.arange(1, n + 1)
    return (2 * (idx * a).sum()) / (n * total) - (n + 1) / n

# Prepara DataFrames para cálculos
@st.cache_data
def processar_dataframes(df_props, out_iqr, out_err):
    df_with = df_props.copy()
    df_no = df_props.drop(pd.concat([out_iqr, out_err]).drop_duplicates().index)
    return df_with, df_no

def contar_lotes(df_with, df_no):
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
            cnt=("area", "count"),
            gini_area=("area", gini),
          )
          .reset_index()
    )

# Função para gerar gráfico circular do Gini
def gerar_grafico_circular(valor, tamanho=100):
    if pd.isna(valor):
        return "<div>Sem dados</div>"
    valor_str = f"{valor:.2%}".replace(".", ",")
    valor_abs = f"{valor:.4f}".replace(".", ",")
    html = f"""
    <style>
    .grafico {{
        --porcentagem: {valor:.2f};
        --tamanho: {tamanho}px;
        width: var(--tamanho);
        height: var(--tamanho);
        border-radius: 50%;
        background: conic-gradient(
            #6e1111 0%,
            #f5e1df calc(var(--porcentagem) * 100%),
            #fcf1f0 0%
        );
        display: grid; place-items: center; margin: 10px auto;
    }}
    .grafico::before {{
        content: "{valor_str}";
        display: grid; place-items: center;
        width: 70%; height: 70%; background: white; border-radius: 50%;
        color: #0c0906; font-size: {tamanho * 0.15}px;
    }}
    </style>
    <div class="grafico" data-value="{valor:.0%}"></div>
    <p style='text-align:center;color:black;'>Valor absoluto: {valor_abs}</p>
    """
    return html

# Estilo de polígonos (sem cache)
def style_fn(f):
    p = f["properties"]
    cnt = p.get("cnt")
    if cnt and cnt < 100:
        return {"fillColor": "#90EE90", "color": "black", "weight": 0.5, "fillOpacity": 0.8}
    g = p.get("gini_area")
    if pd.isna(g):
        return {"fillColor": "#D3D3D3", "color": "black", "weight": 0.5, "fillOpacity": 0.8}
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

# Renderização de mapas com clique habilitado
def render_map(tab, geo_df):
    with tab:
        m = folium.Map(location=[-5.2, -39.5], zoom_start=8, tiles="cartodbpositron")
        tooltip = GeoJsonTooltip(
            fields=["nome_municipio_original", "gini_area", "cnt"],
            aliases=["Município: ", "Índice de Gini: ", "Imóveis: "],
            localize=True, sticky=True,
        )
        folium.GeoJson(geo_df, style_function=style_fn, tooltip=tooltip, name="gini_map").add_to(m)
        for _, row in geo_df.iterrows():
            geom = row.geometry
            if isinstance(geom, (Polygon, MultiPolygon)):
                c = geom.centroid
                folium.map.Marker(
                    [c.y, c.x],
                    icon=folium.DivIcon(html=f"<div style='font-size:6pt;font-weight:bold;color:black;text-shadow:0 0 4px white;'>{row['nome_municipio']}</div>"),
                ).add_to(m)
        legend_html = """
            <div style='position:fixed;top:10px;right:10px;background:white;padding:10px;border:1px solid grey;font-size:14px;z-index:9999;'>
            <b>Intervalos de Gini</b><br>
            <i style='background:#90EE90;width:12px;height:12px;float:left;margin-right:4px'></i> <100 imóveis<br>
            <i style='background:#f9c0ba;width:12px;height:12px;float:left;margin-right:4px'></i>≤0.700<br>
            <i style='background:#d8948c;width:12px;height:12px;float:left;margin-right:4px'></i>0.701–0.800<br>
            <i style='background:#b66960;width:12px;height:12px;float:left;margin-right:4px'></i>0.801–0.850<br>
            <i style='background:#923f37;width:12px;height:12px;float:left;margin-right:4px'></i>0.851–0.900<br>
            <i style='background:#6e1111;width:12px;height:12px;float:left;margin-right:4px'></i>>0.900<br>
            <i style='background:#D3D3D3;width:12px;height:12px;float:left;margin-right:4px'></i>Sem dados
            </div>"""
        m.get_root().html.add_child(folium.Element(legend_html))
        MiniMap(toggle_display=True).add_to(m)
        Fullscreen().add_to(m)
        return st_folium(
            m, 
            width=1024, 
            height=720, 
            returned_objects=["last_object_clicked_tooltip"], 
            use_container_width=True
            )

def render_view_gini_map(df_props, municipios, clicou=False):
    
    # Detecção de outliers
    areas = df_props["area"]
    Q1, Q3 = areas.quantile([0.25, 0.75])
    IQR = Q3 - Q1
    out_iqr = df_props[(areas < Q1 - 1.5 * IQR) | (areas > Q3 + 1.5 * IQR)]
    HALF_STATE_HA = 1488860 / 2
    out_err = df_props[df_props["area"] >= HALF_STATE_HA]
    df_with, df_no = processar_dataframes(df_props, out_iqr, out_err)
    df_with, df_no, warning_munis = contar_lotes(df_with, df_no)

    gini_with = calc_gini_df(df_with)
    gini_with_filt = gini_with[gini_with["cnt"] >= 1]
    state_gini = gini(df_with["area"].values)
    geo_with = municipios.merge(gini_with, on="nome_municipio", how="left")

    col1, col2 = st.columns([7, 3])
    map_data = render_map(col1, geo_with)
    clicou = False
    
    # Sofrimento e dor para descobrir este parâmetro "last_object_clicked_tooltip" (se usar o "last_object_clicked", ele retorna somente Lat e Lon)
    # e mais sofrimento para descobrir que ele retorna 
    # uma string grande que teria que ser "fatiada"
    # Deixo aqui este registro para que outros não sofram tanto quanto eu sofri
    # Se o mapa foi clicado e contém dados, processa o clique
    # e as informações do tooltip são apssadas como string com apenas um "\n" entre elas
    # no formato:
    """
    Aracoiaba
    
    Índice Gini: 
    
    0.7890
    
    Quantidade de imóveis: 
    
    1500
    """
    
    
    clicked_data = map_data.get("last_object_clicked_tooltip") if map_data else None
    # Limpa e extrai os dados da string recebida pelo método get("last_object_clicked_tooltip"), depois desenha o gráfico circular
    if 'gini_estadual_clicado' not in st.session_state:
        st.session_state.gini_estadual_clicado = clicou

    with col2:
        st.subheader("Índice de Gini")
        ## Exibe gráfico circular do Gini de um municipio específico   
        if clicked_data and not st.session_state.gini_estadual_clicado:
            ## Remove linhas vazias e espaços extras
            lines = [line.strip() for line in clicked_data.split("\n") if line.strip()]

            ## Extrai os valores
            municipio = lines[1] if len(lines) > 1 else None
            gini_mun_str = lines[3].replace(",", ".")
            gini_mun = float(gini_mun_str) if gini_mun_str else None
            st.markdown(f"<p style='text-align: center; color:black;'>{municipio}</p>", unsafe_allow_html=True)
            if gini_mun is not None:
                st.markdown(gerar_grafico_circular(gini_mun, 150), unsafe_allow_html=True)
                if st.button("Mostrar Gini Estadual Completo", key="mostrar_gini_estadual_completo", use_container_width=True):
                    st.session_state.gini_estadual_clicado = True
                    st.rerun()
        else:
            st.markdown(gerar_grafico_circular(state_gini, 150), unsafe_allow_html=True)
            st.session_state.gini_estadual_clicado = False

        st.subheader("Gini por Região Administrativa")
        regioes = gini_with_filt["regiao_administrativa"].unique().tolist()
        regiao_selecionada = st.selectbox("Filtrar por Região:", options=["Todas"] + sorted(regioes), index=0)
        if regiao_selecionada != "Todas":
            df_tabela = gini_with_filt[gini_with_filt["regiao_administrativa"] == regiao_selecionada]
        else:
            df_tabela = gini_with_filt
        st.dataframe(
            df_tabela[["regiao_administrativa", "nome_municipio_original", "cnt", "gini_area"]]
            .rename(columns={
                "regiao_administrativa": "Região",
                "nome_municipio_original": "Município",
                "gini_area": "Gini",
                "cnt": "Qtd. Lotes",
            })
            .sort_values("Gini", ascending=False),
            use_container_width=True, hide_index=True, height=600
        )    
    return clicou
    # if st.sidebar.button("Mostrar Gini Estadual Completo"):
    #     st.subheader("Distribuição Fundiária")
    #     st.markdown(gerar_grafico_circular(gini_mun, 200), unsafe_allow_html=True)

    #     st.subheader("Distribuição de Áreas Fundiárias")
    #     bins = [0, 10, 50, 100, 500, 1000, float('inf')]
    #     labels = ['<10 ha', '10-50 ha', '50-100 ha', '100-500 ha', '500-1000 ha', '>1000 ha']
    #     df_areas = df_with.copy()
    #     df_areas['faixa'] = pd.cut(df_areas['area'], bins=bins, labels=labels)
    #     area_dist = df_areas['faixa'].value_counts().sort_index()
    #     st.bar_chart(area_dist)




