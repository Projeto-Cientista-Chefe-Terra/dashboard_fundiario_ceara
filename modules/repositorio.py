# modules/repositorio.py
"""Acesso aos dados do miniserver, com uma função cacheada por endpoint.

Regras de cache:

- ``st.cache_data`` para respostas JSON: cada chamada recebe uma cópia, então a
  página pode alterar o resultado sem afetar outras sessões.
- ``st.cache_resource`` para os DataFrames grandes (lotes e limites): o mesmo
  objeto é compartilhado por todas as sessões para não copiar dezenas de
  milhares de linhas a cada interação. **Trate-os como somente leitura** e faça
  ``.copy()`` antes de qualquer alteração.

Todas expiram em ``config.TTL_DADOS``. Antes de cada consulta, o repositório
confere a versão dos dados no miniserver (``/versao_dados``, cacheada por
``config.TTL_VERSAO``). Se ela mudou, os caches daqui são descartados e a carga
nova aparece na interação seguinte. As funções derivadas recebem a versão dos
dados (``versaoDados``) como chave, para nunca misturar cargas.
"""

import functools
import logging
import time

import geopandas as gpd
import pandas as pd
import streamlit as st

from modules import apiCliente, config
from modules.classificacao import prepararLotesClassificados

logger = logging.getLogger(__name__)

# Colunas devolvidas por /dados_fundiarios (o endpoint não traz geometria).
COLUNAS_LOTES = [
    "imovel", "data_criacao_lote", "numero_incra", "numero_lote", "numero_titulo",
    "area", "modulo_fiscal", "situacao_juridica", "categoria", "regiao_administrativa",
    "nome_municipio", "nome_municipio_original", "nome_distrito", "nome_proprietario",
    "id_proprietario",
]

GEOJSON_VAZIO = {"type": "FeatureCollection", "features": []}


_CACHES_DE_DADOS: list = []
_versaoConhecida: str | None = None


@st.cache_data(ttl=config.TTL_VERSAO, show_spinner=False)
def carregarVersaoDados() -> str:
    """Versão da carga mais recente no miniserver, ou "" se ele não informar."""
    try:
        dados = apiCliente.buscarJson("versao_dados", permitir404=True)
    except apiCliente.ErroApi:
        return ""
    return str((dados or {}).get("versao") or "")


def sincronizarVersaoDados() -> None:
    """Descarta os caches de dados quando o miniserver passa a ter uma carga nova."""
    global _versaoConhecida
    versao = carregarVersaoDados()
    if not versao:
        return
    if _versaoConhecida and versao != _versaoConhecida:
        logger.info("Nova carga de dados no miniserver (%s); descartando o cache.", versao)
        for funcao in _CACHES_DE_DADOS:
            funcao.clear()
    _versaoConhecida = versao


def _conferindoVersao(funcao):
    """Confere a versão dos dados antes de usar o cache da função."""
    _CACHES_DE_DADOS.append(funcao)

    @functools.wraps(funcao)
    def envoltorio(*args, **kwargs):
        sincronizarVersaoDados()
        return funcao(*args, **kwargs)

    envoltorio.clear = funcao.clear
    return envoltorio


def versaoDados(df: pd.DataFrame) -> float:
    """Identificador da carga que originou o DataFrame, usado como chave de cache."""
    return df.attrs.get("versao", 0.0)


@_conferindoVersao
@st.cache_data(ttl=config.TTL_DADOS, show_spinner=False)
def carregarRegioes() -> list[str]:
    return apiCliente.buscarJson("regioes").get("regioes", [])


@_conferindoVersao
@st.cache_data(ttl=config.TTL_DADOS, show_spinner=False)
def carregarMunicipiosDaRegiao(regiao: str) -> list[str]:
    dados = apiCliente.buscarJson("municipios", {"regiao": regiao}, permitir404=True)
    return (dados or {}).get("municipios", [])


@_conferindoVersao
@st.cache_data(ttl=config.TTL_DADOS, show_spinner="Carregando limites municipais...")
def carregarLimitesMunicipais() -> dict:
    """GeoJSON com o limite de todos os municípios, numa única requisição."""
    return apiCliente.buscarJson("geojson_muni", {"municipio": "todos"})


@_conferindoVersao
@st.cache_resource(ttl=config.TTL_DADOS, show_spinner=False)
def carregarLimitesMunicipaisGdf() -> gpd.GeoDataFrame:
    """Limites municipais como GeoDataFrame. Compartilhado: somente leitura."""
    features = carregarLimitesMunicipais().get("features", [])
    if not features:
        return gpd.GeoDataFrame({"nome_municipio": []}, geometry=[], crs="EPSG:4326")
    return gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")


def filtrarLimites(limites: dict, municipios) -> dict:
    """Recorte do GeoJSON de limites com os municípios indicados."""
    alvo = set(municipios)
    return {
        "type": "FeatureCollection",
        "features": [f for f in limites.get("features", []) if f.get("properties", {}).get("nome_municipio") in alvo],
    }


@_conferindoVersao
@st.cache_resource(ttl=config.TTL_DADOS, show_spinner="Carregando dados fundiários...")
def carregarLotes() -> pd.DataFrame:
    """Todos os imóveis do estado, uma requisição por região. Compartilhado: somente leitura."""
    regioes = carregarRegioes()
    registros, falhas = [], []
    for regiao in regioes:
        try:
            dados = apiCliente.buscarJson("dados_fundiarios", {"regiao": regiao}, permitir404=True)
        except apiCliente.ErroApi:
            falhas.append(regiao)
            continue
        if isinstance(dados, list):
            registros.extend(dados)
    if regioes and len(falhas) == len(regioes):
        raise apiCliente.ErroApi("dados_fundiarios", "nenhuma região pôde ser carregada")
    if falhas:
        logger.warning("Regiões sem dados por falha na API: %s", ", ".join(falhas))

    df = pd.DataFrame.from_records(registros).reindex(columns=COLUNAS_LOTES)
    for coluna in ("area", "modulo_fiscal"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    df.attrs["versao"] = time.time()
    df.attrs["regioesComFalha"] = falhas
    return df


@st.cache_resource(ttl=config.TTL_DADOS, show_spinner=False, max_entries=2)
def _classificarLotes(versao: float, _lotes: pd.DataFrame) -> pd.DataFrame:
    dfClassificado = prepararLotesClassificados(_lotes)
    dfClassificado.attrs["versao"] = versao
    return dfClassificado


_CACHES_DE_DADOS.append(_classificarLotes)


def carregarLotesClassificados() -> pd.DataFrame:
    """Imóveis com área e módulo fiscal válidos e a coluna ``categoria``. Somente leitura."""
    lotes = carregarLotes()
    return _classificarLotes(versaoDados(lotes), lotes)


@_conferindoVersao
@st.cache_data(ttl=config.TTL_DADOS, show_spinner="Carregando imóveis...")
def carregarGeojsonLotes(regiao: str | None = None, municipio: str | None = None) -> dict:
    """Polígonos dos imóveis de uma região ou de um município, simplificados no servidor."""
    parametros = {"regiao": regiao} if regiao else {"municipio": municipio}
    return apiCliente.buscarJson("geojson", parametros, permitir404=True) or GEOJSON_VAZIO


def carregarGeojsonLotesSemSimplificacao(regiao: str | None = None, municipio: str | None = None) -> dict:
    """Polígonos originais dos imóveis de uma região ou de um município, para exportação.

    Sem cache: o resultado é grande e só serve para montar o pacote do QGIS, que
    ``paginaExportarQgis`` guarda em cache já pronto.
    """
    parametros = {"regiao": regiao} if regiao else {"municipio": municipio}
    parametros["tolerance"] = 0
    return apiCliente.buscarJson("geojson", parametros, permitir404=True) or GEOJSON_VAZIO


@_conferindoVersao
@st.cache_data(ttl=config.TTL_DADOS, show_spinner="Carregando assentamentos...")
def carregarAssentamentos(municipio: str = "todos", tolerancia: float | None = None) -> dict:
    parametros = {"municipio": municipio}
    if tolerancia is not None:
        parametros["tolerance"] = tolerancia
    return apiCliente.buscarJson("geojson_assentamentos", parametros, permitir404=True) or GEOJSON_VAZIO


@_conferindoVersao
@st.cache_data(ttl=config.TTL_DADOS, show_spinner=False)
def carregarMunicipiosComAssentamento() -> list[str]:
    return apiCliente.buscarJson("assentamentos_municipios").get("municipios", [])


@_conferindoVersao
@st.cache_data(ttl=config.TTL_DADOS, show_spinner="Carregando reservatórios...")
def carregarReservatorios(municipio: str = "todos") -> dict:
    return apiCliente.buscarJson("geojson_reservatorios", {"municipio": municipio}, permitir404=True) or GEOJSON_VAZIO


@_conferindoVersao
@st.cache_data(ttl=config.TTL_DADOS, show_spinner=False)
def carregarMunicipiosComReservatorio() -> list[str]:
    return apiCliente.buscarJson("reservatorios_municipios").get("municipios", [])
