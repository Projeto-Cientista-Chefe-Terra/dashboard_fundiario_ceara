# app.py

# OBservações
#  st_folium(m, width=1000, height=900, returned_objects=[]) returned_objects -> serve para o mapa não
# use_container_width=True -> serve para usar todo o width disponível
# retornar nada.

import streamlit as st
from streamlit_folium import st_folium
import folium
from typing import TypedDict

class DebugInfo(TypedDict):
    municipios_recebidos: int
    municipios_com_dados: int | None  # None até ser calculado
    municipios_sem_dados: int | None



from modules import (
    load_csv_data as load_data,
    load_municipios,
    validate_data,
    load_municipios,
    render_view_assentamento_map,
    render_view_gini_map,
    render_view_grafico_interativo,
    render_view_mapa_interativo,
    render_view_predominancia_map,
    render_view_reservatorios_map
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

# Cacheia GeoDataFrame de municípios e preparação de contexto
load_municipios = st.cache_resource()(load_municipios)


# -----------------------------
# 🚀 App Streamlit
# -----------------------------

# ---------------------------------------------------
# 0) Definição de funções de visualizações
# ---------------------------------------------------



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
dados_fundiarios = load_data("")
contorno_municipios = load_municipios("")


######################### Gráficos de Tabelas Gerais do Estado #########################
def graficos_e_quadros():
    render_view_grafico_interativo(df_class)


######################### Mapa de Predominância #########################
def mapa_de_Predominância(dados_fundiarios, contorno_municipios):
    render_view_predominancia_map(dados_fundiarios, contorno_municipios)


######################### Mapa Interativo da Malha Fundiária #########################
#TODO Inserir o nome dos municipipios na camada de delimitacao dos municipio (fazer em todos os mapas)
def mapa_interativo():
    render_view_mapa_interativo()


######################### Mapa de Gini do Estado #########################
#TODO Inserir o nome dos municipios e os limitadores em todos os municipios
def mapa_gini(dados_fundiarios, contorno_municipios):
    render_view_gini_map(dados_fundiarios, contorno_municipios)


######################### Mapa de Assentamentos do Estado ######################
def mapa_Assentamentos():
    render_view_assentamento_map()


######################### Mapa de Hidrográfico do Estado #######################
def mapa_hidrográfico():
    render_view_reservatorios_map()



######################### Sobre o projeto  #######################
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
    st.image("./assets/Logos.png", use_container_width=True)
    col1, col2, col3, col4 = st.columns(4, vertical_alignment='center', )

    # with col1:
    #     st.image("./assets/Idace.png", width=150)
        
    # with col2:
    #     st.image("./assets/CC_Terra.png", width=150)

    # with col3:
    #     st.image("./assets/funcap.png", width=250)
        
    # with col4:
    #     st.image("./assets/ufc_logo.png", width=150)



######################### Estrutura Geral de Navegação #########################
# ---------------------------------------------------
# 1) set_page_config deve ser o primeiro comando do Streamlit
# ---------------------------------------------------
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown(
    "# Terra.Ce",
    unsafe_allow_html=True,
)


if "current_page" not in st.session_state:
    st.session_state.current_page = "Gráficos"

with st.sidebar:
    st.header("")
    # CSS para ícones Font Awesome
    if st.button(
        "Gráficos e Quadros", use_container_width=True, icon=":material/bar_chart:"
    ):
        st.session_state.current_page = "Gráficos"
    if st.button(
        "Mapa de Predominância", use_container_width=True, icon=":material/location_on:"
    ):
        st.session_state.current_page = "Mapa de Predominância"
    if st.button("Mapa da Malha Fundiária", use_container_width=True, icon=":material/map:"):
        st.session_state.current_page = "Mapa da Malha Fundiária"

    if st.button("Mapa de Concentração Fundiária", use_container_width=True, icon=":material/crisis_alert:"):
        st.session_state.current_page = "Mapa de Concentração Fundiária"

    if st.button("Mapa de Assentamentos", use_container_width=True, icon=":material/globe_location_pin:"):
        st.session_state.current_page = "Mapa de Assentamento"
    
    if st.button("Mapa Hidrográfico", use_container_width=True, icon=":material/water_drop:"):
        st.session_state.current_page = "Mapa Hidrografico"

    if st.button("Sobre", use_container_width=True, icon=":material/info:"):
        st.session_state.current_page = "Sobre"


# ---------------------------------------------------
# 6) Navegação
# ---------------------------------------------------


st.logo("./assets/logo_idace_instagram.png", size="large")
# ---------------------------------------------------
# 7) Lógica de cada aba
# ---------------------------------------------------
if st.session_state.current_page == "Gráficos":
    st.title("").markdown("### Gráficos e Quadros")
    graficos_e_quadros()

elif st.session_state.current_page == "Mapa de Predominância":
    st.title("").markdown("### Mapa de Predominância do Tipo de  Imóvel por Município",
                        unsafe_allow_html=True, help=
                        """**O que esse mapa é:**  
                            
                            """)
    mapa_de_Predominância(dados_fundiarios, contorno_municipios)

elif st.session_state.current_page == "Mapa da Malha Fundiária":
    st.title("").markdown("### Mapa da Malha Fundiária",
                        unsafe_allow_html=True, help=
                        """**O que esse mapa é:**  
                            
                            """)
    mapa_interativo()

elif st.session_state.current_page == "Mapa de Concentração Fundiária":
    st.title("").markdown("### Mapa de Concentração Fundiária do Ceará",
                        unsafe_allow_html=True, help=
                        """**O que esse mapa é:**  
                           
                           """)
    mapa_gini(dados_fundiarios, contorno_municipios)

elif st.session_state.current_page == "Mapa Hidrografico":
    st.title("").markdown("### Mapa Hidrográfico",
                        unsafe_allow_html=True, help=
                        """**O que esse mapa é:**  
                           """)
    mapa_hidrográfico()
elif st.session_state.current_page == "Mapa de Assentamento":
    st.title("").markdown("### Mapa de Assentamentos",
                        unsafe_allow_html=True, help=
                        """**O que esse mapa é:**  
                          """)
    mapa_Assentamentos()

elif st.session_state.current_page == "Sobre":
    st.title("").markdown("### Sobre")
    sobre()
