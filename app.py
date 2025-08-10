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
    render_view_reservatorios_map,
)


# Configurações
DATA_SERVICE_URL = st.secrets.get("DATA_SERVICE_URL", "http://localhost:8000")
# MAX_FEATURES = 500  # Limite para features simultâneas

st.set_page_config(
    page_title="Dashboard",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------
# 🔒 Aplicação de Cache
# -----------------------------

# Cacheia a leitura de CSVs e DataFrames pesados (expira em 1h)
load_data = st.cache_resource(ttl=3600)(load_data)

# Cacheia validações e splits de dados (poupando re-execuções)
validate_data = st.cache_resource()(validate_data)

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
# TODO Inserir o nome dos municipipios na camada de delimitacao dos municipio (fazer em todos os mapas)
def mapa_interativo():
    render_view_mapa_interativo()


######################### Mapa de Gini do Estado #########################
# TODO Inserir o nome dos municipios e os limitadores em todos os municipios
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
    with st.container():
        st.html("""<div class="teste"></div>""")
        st.markdown(
            """
        Aplicação de painéis contendo dados estatísticos e geoespaciais da malha fundiária cearense desenvolvido, principalmente, a partir dos dados cadastrados no Instituto de Desenvolvimento Agrário do Ceará (IDACE). Este software faz parte das ações realizadas no âmbito do projeto **Cientista Chefe Terra  de Governança Fundiária e Ambiental**, parceria entre o IDACE, a Universidade Federal do Ceará (UFC) e a Fundação Cearense de Apoio ao Desenvolvimento Científico e Tecnológico (Funcap).
        """
        )

        # Coordenadora Geral
        st.subheader("Coordenadora Geral")
        st.markdown(
            """    
        Profa. Maria Inês Escobar da Costa (UFC)
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
        col1, col2, col3, col4 = st.columns(
            4,
            vertical_alignment="center",
        )

    # with col1:
    #     st.image("./assets/Idace.png", width=150)

    # with col2:
    #     st.image("./assets/CC_Terra.png", width=150)

    # with col3:
    #     st.image("./assets/funcap.png", width=250)

    # with col4:
    #     st.image("./assets/ufc_logo.png", width=150)


######################### Landing Page  #######################
def landing_page():
    # ! Depois de finalizar, retornar
    # if st.button("Acessar a plataforma Terra.Ce"):
    #     st.session_state.current_page = "Gráficos"
    #     st.rerun()
    
    with st.container():
        
        # st.image("https://www.idace.ce.gov.br/wp-content/uploads/sites/84/2025/07/368A8108-768x512.jpg", use_container_width=True)
        st.markdown(
            """
            <div class="minha-div">
                <img src="https://i.imgur.com/6Hk77Gg.png" alt="Imagem do IDACE">
            </div>
            <div class="minha-div">
                <img src="https://i.imgur.com/N1Ymd3d.png" alt="Imagem do IDACE">
            </div>
            """,
            unsafe_allow_html=True
        )
        st.html("""
        
        <div class="container-estilizado">
            <!-- Primeira Seção -->
            <div>
                <h3>Equipe Idace</h3>
                <span ></span>
                <span ></span>

                <span class="titulo">Superintendente</span>
                <span class="subtitulo">João Alfredo Telles Melo</span>
                
                <span class="titulo">Superintendente Adjunto</span>
                <span class="subtitulo">Antônio Rodrigues de Amorim</span>
            </div>
            
            <!-- Segunda Seção -->
            <div>
                <span class="titulo">Diretora Administrativo-Financeira</span>
                <span class="subtitulo">Claudecilia de Oliveira Teixeira</span>
                
                <span class="titulo">Diretor Técnico de Operações</span>
                <span class="subtitulo">Paulo H. Magalhães Lobo</span>
                
                <span class="titulo">Assessor Jurídico</span>
                <span class="subtitulo">Ricardo Sá Benevides Magalhães</span>
            </div>
            
            <!-- Terceira Seção (Imagem como link) -->
            
                <a href="https://drive.google.com/file/d/1pdqD_55RAo3UNkp7ggx1MUGcKaH0UtSZ/view?usp=drive_link" target="_blank">
                    <img src="https://www.idace.ce.gov.br/wp-content/uploads/sites/84/2021/07/idace_apresentacao_banner.png" alt="Imagem" class="imagem-link">
                </a>
            
        </div>
        """)
        st.html("""
                <div class="container-estilizado2">
                <h4>Bem-vindo(a) à Terra.Ce</h4>
                <p> 
                    “A plataforma Terra.CE é fruto de uma parceria de inovação pública entre IDACE a  Universidade Federal do Ceará e a FUNCAP. A sistematização dos dados aqui apresentados é fruto do Projeto Cientista Chefe Governança Fundiária e Ambiental - CCTERRA, que visa fortalecer a gestão da terra no Ceará por meio da pesquisa e da ciência de dados. Esta plataforma disponibiliza indicadores e mapas interativos para subsidiar políticas públicas baseadas em evidências, promovendo uma governança integrada, sustentável e transparente. Compreender as dinâmicas territoriais é essencial para um Ceará mais justo social e ambientalmente.”
                </p>
                </div>
                """)
        st.html("""
        
        <div class="container-estilizado ">
            <!-- Primeira Seção -->
            <div>
                <h3>Equipe TerraCE</h3>
                <span class="titulo">Coordenadora do Projeto/UFC</span>
                <span class="subtitulo">Maria Inês Escobar da Coêla</span>

                <span class="titulo">Coordenador Técnico de Sistemas/UFC</span>
                <span class="subtitulo">Wellington Wagner Ferreira Sarmento</span>

                <span class="titulo">Coordenadora de Análises Quantitativas/UFC</span>
                <span class="subtitulo">Maria de Nazaré Moraes Soares</span>

                <span class="titulo">Coordenadora de Análises Qualitativas/UFC</span>
                <span class="subtitulo">Kelly Maria Gomes Menezes</span>

                <span class="titulo">Coordenadora de Ações de Campo</span>
                <span class="subtitulo">Christine Farias Coelho</span>

                <span class="titulo">Pesquisadora</span>
                <span class="subtitulo">Erika Roanna da Silva</span>
            </div>
            
            <!-- Segunda Seção -->
            <div>
                <span class="titulo">Pesquisadora</span>
                <span class="subtitulo">Bárbara Sheyla Pereira Lima Moreira</span>

                <span class="titulo">Pesquisador</span>
                <span class="subtitulo">Bruno Silva Pereira</span>

                <span class="titulo">Pesquisador</span>
                <span class="subtitulo">André Lucas de Oliveira Domingues</span>

                <span class="titulo">Pesquisador</span>
                <span class="subtitulo">Wesley Barbosa Martins Ribeiro</span>

                <span class="titulo">Pesquisadora</span>
                <span class="subtitulo">Juliana Azevedo da Silva</span>

                <span class="titulo">Pesquisador</span>
                <span class="subtitulo">Fernando Abreu</span>
            </div>
            
        </div>
        """)
        st.html("""<section class="AcessoRapido">
      <div class="wrapper">
        <div class="row">
          <h4>Acesso Rápido</h4>

          <nav class="MenuAcessos">
            <div class="acesso-rapido">
              <ul id="menu-acesso-rapido-footer" class="menu">
                <li
                  id="menu-item-870"
                  class="portal menu-item menu-item-type-custom menu-item-object-custom menu-item-870"
                >
                  <a href="https://cearatransparente.ce.gov.br" target="_blank"
                    ><i class="PortalTransparencia"></i>
                    <span>
                      Ceará<br />
                      Transparente
                    </span>
                  </a>
                </li>
                <li
                  id="menu-item-871"
                  class="acesso menu-item menu-item-type-custom menu-item-object-custom menu-item-871"
                >
                  <a href="http://cartadeservicos.ce.gov.br/" target="_blank"
                    ><i class="AcessoCidadao"></i>
                    <span> Carta de Serviços<br />do Cidadão </span>
                  </a>
                </li>
                <li
                  id="menu-item-872"
                  class="lei menu-item menu-item-type-custom menu-item-object-custom menu-item-872"
                >
                  <a
                    href="https://cearatransparente.ce.gov.br/portal-da-transparencia/acesso-a-informacao?locale=pt-BR"
                    target="_blank"
                    ><i class="AcessoInformacao"></i>
                    <span>
                      Lei geral de<br />
                      acesso à informação
                    </span>
                  </a>
                </li>
                <li
                  id="menu-item-873"
                  class="diario menu-item menu-item-type-custom menu-item-object-custom menu-item-873"
                >
                  <a
                    href="http://pesquisa.doe.seplag.ce.gov.br/"
                    target="_blank"
                    ><i class="DiarioOficial"></i>

                    <span>
                      Diário<br />
                      Oficial
                    </span>
                  </a>
                </li>
                <li
                  id="menu-item-874"
                  class="legislacao menu-item menu-item-type-custom menu-item-object-custom menu-item-874"
                >
                  <a href="https://www.al.ce.gov.br/" target="_blank"
                    ><i class="Legislacao"></i>

                    <span>
                      Legislação<br />
                      Estadual
                    </span>
                  </a>
                </li>
                <li
                  id="menu-item-61919"
                  class="acoes menu-item menu-item-type-post_type menu-item-object-page menu-item-61919"
                >
                  <a
                    href="https://www.ceara.gov.br/wp-content/uploads/2025/07/Codigo-de-Etica.pdf"
                    target="_blank"
                    ><i class="AcoesGoverno"></i>
                    <span> Código de Ética dos Servidores Públicos </span>
                  </a>
                </li>
              </ul>
            </div>
          </nav>
        </div>
      </div>
    </section>
    <footer>
      <div class="wrapper">
        <div class="row Infos" style="border-top: none">
          <div class="dt-2 NomeSite">
            <a class="link-gov" href="http://WWW.IDACE.CE.GOV.BR">
              <h2>IDACE.CE.GOV.BR</h2>
            </a>
          </div>

          <div class="dt-10 Direitos">
            <div>
              <div class="textwidget">
                <div class="box">
                  <h2>IDACE</h2>
                  <p>
                    Av. Bezerra de Menezes, 1820 - São Gerardo<br />
                    Fortaleza, CE<br />
                    CEP: 60.325-001
                  </p>
                </div>
                <div class="box">
                  <h2>Horário de Atendimento</h2>
                  <p>8h às 12h</p>
                  <p>13h às 17h</p>
                </div>

                <div class="box">
                  <h2 class="canais">Nossos canais</h2>
                  <div class="redes">
                    <ul class="menu">
                      <li class="facebook redesLinkRodape">
                        <a
                          href="https://www.facebook.com/idace.gov"
                          style="overflow: hidden"
                          target="_blank"
                          >Facebook</a
                        >
                      </li>
                      <li class="instagram redesLinkRodape">
                        <a
                          href="https://www.instagram.com/idace.ce/"
                          style="overflow: hidden"
                          target="_blank"
                          >Instagram</a
                        >
                      </li>
                    </ul>
                  </div>
                </div>

                <div class="box copyright">
                  <p>
                    © 2017 - 2025 – governo do estado do ceará<br />
                    todos os direitos reservados
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>""")



######################### Estrutura Geral de Navegação #########################
# ---------------------------------------------------
# 1) set_page_config deve ser o primeiro comando do Streamlit
# ---------------------------------------------------
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


st.logo("./assets/Frame 18.png", size="large")
if "current_page" not in st.session_state:
    st.session_state.current_page = "Inicio"



# if st.session_state.current_page != 'Inicio':
    # st.logo("./assets/Frame 18.png", size="large")
with st.sidebar:
    # st.header("")
    # CSS para ícones Font Awesome
    if st.button(
        "Início", use_container_width=True, icon=":material/home:"
    ):
        st.session_state.current_page = "Inicio"
        st.rerun()
    if st.button(
        "Gráficos e Quadros", use_container_width=True, icon=":material/bar_chart:"
    ):
        st.session_state.current_page = "Gráficos"
    if st.button(
        "Mapa de Predominância", use_container_width=True, icon=":material/location_on:"
    ):
        st.session_state.current_page = "Mapa de Predominância"
    if st.button(
        "Mapa da Malha Fundiária", use_container_width=True, icon=":material/map:"
    ):
        st.session_state.current_page = "Mapa da Malha Fundiária"

    if st.button(
        "Mapa de Concentração Fundiária",
        use_container_width=True,
        icon=":material/crisis_alert:",
    ):
        st.session_state.current_page = "Mapa de Concentração Fundiária"

    if st.button(
        "Mapa de Assentamentos",
        use_container_width=True,
        icon=":material/globe_location_pin:",
    ):
        st.session_state.current_page = "Mapa de Assentamento"

    if st.button(
        "Mapa Hidrográfico", use_container_width=True, icon=":material/water_drop:"
    ):
        st.session_state.current_page = "Mapa Hidrografico"

    if st.button("Sobre", use_container_width=True, icon=":material/info:"):
        st.session_state.current_page = "Sobre"


# ---------------------------------------------------
# 6) Navegação
# ---------------------------------------------------


# ---------------------------------------------------
# 7) Lógica de cada aba
# ---------------------------------------------------
if st.session_state.current_page == "Inicio":
    landing_page()
    
elif st.session_state.current_page == "Gráficos":
    st.title("").markdown("## Gráficos e Quadros")
    graficos_e_quadros()

elif st.session_state.current_page == "Mapa de Predominância":
    st.title("").markdown(
        "## Mapa de Predominância do Tipo de  Imóvel por Município",
        unsafe_allow_html=True,
    )
    mapa_de_Predominância(dados_fundiarios, contorno_municipios)

elif st.session_state.current_page == "Mapa da Malha Fundiária":
    st.title("").markdown(
        "## Mapa da Malha Fundiária",
        unsafe_allow_html=True,
    )
    mapa_interativo()

elif st.session_state.current_page == "Mapa de Concentração Fundiária":
    st.title("").markdown(
        "## Mapa de Concentração Fundiária do Ceará",
        unsafe_allow_html=True,
    )
    mapa_gini(dados_fundiarios, contorno_municipios)

elif st.session_state.current_page == "Mapa Hidrografico":
    st.title("").markdown(
        "## Mapa Hidrográfico",
        unsafe_allow_html=True,
    )
    mapa_hidrográfico()
elif st.session_state.current_page == "Mapa de Assentamento":
    st.title("").markdown(
        "## Mapa de Assentamentos",
        unsafe_allow_html=True,
    )
    mapa_Assentamentos()

elif st.session_state.current_page == "Sobre":
    st.title("").markdown("## Sobre")
    sobre()
