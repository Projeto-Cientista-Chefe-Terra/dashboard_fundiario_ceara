# modules/navegacao.py
"""Menu lateral e tabela de páginas do dashboard.

Cada página tem uma chave estável, guardada em ``st.session_state``. O botão da
página ativa é destacado por CSS, usando a classe ``st-key-<chave do botão>``
que o Streamlit põe no contêiner de cada widget com ``key``.
"""

from dataclasses import dataclass
from collections.abc import Callable

import streamlit as st

from modules import (
    paginaAssentamentos, paginaConcentracao, paginaEscolasCampo, paginaExportarQgis, paginaGraficos,
    paginaHidrografia, paginaInicio, paginaMalhaFundiaria, paginaPredominancia, paginaSobre,
)

CHAVE_SESSAO = "paginaAtual"
PREFIXO_BOTAO = "menu-"
COR_BOTAO = "#00824110"
COR_BOTAO_ATIVO = "#E1B87EBC"
COR_BORDA = "#C5CAE9"


@dataclass(frozen=True)
class Pagina:
    chave: str
    rotulo: str
    icone: str
    titulo: str | None
    renderizar: Callable[[], None]


PAGINAS = [
    Pagina("inicio", "Início", ":material/home:", None, paginaInicio.renderizar),
    Pagina("graficos", "Gráficos e Quadros", ":material/bar_chart_4_bars:", "Gráficos e Quadros", paginaGraficos.renderizar),
    Pagina("predominancia", "Mapa de Predominância", ":material/distance:",
           "Mapa de Predominância do Tipo de Imóvel por Município", paginaPredominancia.renderizar),
    Pagina("malhaFundiaria", "Mapa da Malha Fundiária", ":material/map_search:",
           "Mapa da Malha Fundiária", paginaMalhaFundiaria.renderizar),
    Pagina("concentracaoFundiaria", "Mapa de Concentração Fundiária", ":material/crisis_alert:",
           "Mapa de Concentração Fundiária do Ceará", paginaConcentracao.renderizar),
    Pagina("assentamentos", "Mapa de Assentamentos", ":material/globe_location_pin:",
           "Mapa de Assentamentos", paginaAssentamentos.renderizar),
    Pagina("hidrografia", "Mapa Hidrográfico", ":material/water_drop:", "Mapa Hidrográfico", paginaHidrografia.renderizar),
    Pagina("escolasCampo", "Mapa Escolas do Campo", ":material/school:", "Mapa Escolas do Campo", paginaEscolasCampo.renderizar),
    Pagina("exportarQgis", "Exportar para o QGIS", ":material/download:", "Exportar Dados para o QGIS",
           paginaExportarQgis.renderizar),
    Pagina("sobre", "Sobre", ":material/info:", None, paginaSobre.renderizar),
]
PAGINAS_POR_CHAVE = {pagina.chave: pagina for pagina in PAGINAS}


def obterPaginaAtual() -> Pagina:
    chave = st.session_state.setdefault(CHAVE_SESSAO, PAGINAS[0].chave)
    return PAGINAS_POR_CHAVE.get(chave, PAGINAS[0])


def _selecionar(chave: str) -> None:
    st.session_state[CHAVE_SESSAO] = chave


def cssDoMenu(chaveAtiva: str) -> str:
    return (
        f'[class*="st-key-{PREFIXO_BOTAO}"] button {{ background: {COR_BOTAO}; color: #000000; '
        f"border: 1px solid {COR_BORDA}; }}\n"
        f".st-key-{PREFIXO_BOTAO}{chaveAtiva} button {{ background: {COR_BOTAO_ATIVO}; "
        f"border: 1px solid {COR_BOTAO_ATIVO}; }}"
    )


def renderizarMenu(paginaAtual: Pagina) -> None:
    with st.sidebar:
        for pagina in PAGINAS:
            st.button(
                pagina.rotulo,
                icon=pagina.icone,
                key=f"{PREFIXO_BOTAO}{pagina.chave}",
                on_click=_selecionar,
                args=(pagina.chave,),
                width="stretch",
            )
        st.markdown(f"<style>{cssDoMenu(paginaAtual.chave)}</style>", unsafe_allow_html=True)
