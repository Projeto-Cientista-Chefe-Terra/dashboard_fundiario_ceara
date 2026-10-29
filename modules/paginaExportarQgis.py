# modules/paginaExportarQgis.py
"""Página Exportar para o QGIS: pacote com os lotes e os limites municipais de um recorte.

O recorte pode ser um município, uma região administrativa ou o estado. O
pacote é montado por ``exportacaoQgis`` com os dados da API do miniserver: os
polígonos dos lotes vêm sem simplificação (``tolerance=0``), e os limites
municipais, simplificados como no resto do dashboard. Só as colunas de
``COLUNAS_API`` passam para o pacote, então o nome do proprietário não entra.

Cada pacote fica em cache, pela versão dos dados, e é compartilhado entre as
sessões. O do estado leva cerca de um minuto para ser montado na primeira vez.
"""

import geopandas as gpd
import pandas as pd
import shapely.geometry
import streamlit as st

from modules import config, exportacaoQgis, repositorio
from modules.apiCliente import ErroApi
from modules.componentesUi import mostrarErroDados, paragrafoInformativo

RECORTE_MUNICIPIO = "Município"
RECORTE_REGIAO = "Região Administrativa"
RECORTE_ESTADO = "Estado do Ceará"
RECORTES = [RECORTE_MUNICIPIO, RECORTE_REGIAO, RECORTE_ESTADO]
CHAVE_PEDIDO = "exportarQgisPedido"

# Propriedade do GeoJSON da API -> coluna esperada por exportacaoQgis.
COLUNAS_API = {
    "imovel": "nome_lote",
    "data_criacao_lote": "dt_criacao",
    "numero_incra": "num_incra",
    "numero_lote": "num_lote",
    "area": "area_ha",
    "situacao_juridica": "sit_jurid",
    "categoria": "categoria",
}


def lotesDaApi(geojson: dict) -> gpd.GeoDataFrame:
    """Lotes do GeoJSON da API nas colunas de ``exportacaoQgis``, sem nenhuma outra propriedade."""
    features = geojson.get("features", [])
    propriedades = [feature.get("properties") or {} for feature in features]
    dados = pd.DataFrame({novo: [p.get(antigo) for p in propriedades] for antigo, novo in COLUNAS_API.items()})
    dados["chave"] = [exportacaoQgis.normalizarNome(p.get("nome_municipio") or "") for p in propriedades]
    geometrias = [shapely.geometry.shape(f["geometry"]) if f.get("geometry") else None for f in features]
    return gpd.GeoDataFrame(dados, geometry=geometrias, crs="EPSG:4326")


def limitesDaApi(limites: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    chaves = limites["nome_municipio"].map(exportacaoQgis.normalizarNome) if "nome_municipio" in limites else []
    return gpd.GeoDataFrame({"chave": chaves}, geometry=limites.geometry.to_numpy(), crs=limites.crs)


def montarRecorte(tipo: str, regiao: str | None, municipio: str | None) -> exportacaoQgis.Recorte:
    if tipo == RECORTE_ESTADO:
        return exportacaoQgis.recorteEstado()
    if tipo == RECORTE_REGIAO:
        return exportacaoQgis.recorteRegiao(regiao)
    return exportacaoQgis.recorteMunicipio(municipio)


def buscarLotes(tipo: str, regiao: str | None, municipio: str | None) -> gpd.GeoDataFrame:
    """Lotes do recorte pela API. O estado é buscado região por região, como em ``carregarLotes``."""
    if tipo == RECORTE_MUNICIPIO:
        geojsons = [repositorio.carregarGeojsonLotesSemSimplificacao(municipio=municipio)]
    elif tipo == RECORTE_REGIAO:
        geojsons = [repositorio.carregarGeojsonLotesSemSimplificacao(regiao=regiao)]
    else:
        geojsons = [repositorio.carregarGeojsonLotesSemSimplificacao(regiao=r) for r in repositorio.carregarRegioes()]
    return pd.concat([lotesDaApi(g) for g in geojsons], ignore_index=True)


def formatarVersao(versao: str) -> str:
    """'2026-10-27 14:55:40.5+00:00' vira '27/10/2026 11:55', no horário de Fortaleza."""
    momento = pd.to_datetime(versao, errors="coerce", utc=True) if versao else pd.NaT
    if pd.isna(momento):
        return versao or "não informada"
    return momento.tz_convert("America/Fortaleza").strftime("%d/%m/%Y %H:%M")


def textoOrigem(versao: str) -> str:
    return (
        "  Dashboard Fundiário do Ceará, página Exportar para o QGIS, com os dados da API do\n"
        f"  terraGeoDataMiniServer (carga de dados: {formatarVersao(versao)}). A geometria dos\n"
        "  lotes é a da base, sem simplificação. Os limites municipais vêm simplificados pela\n"
        "  API, com tolerância de 0,001 grau (cerca de 100 m)."
    )


@st.cache_resource(ttl=config.TTL_DADOS, max_entries=6, show_spinner=False)
def gerarPacote(tipo: str, regiao: str | None, municipio: str | None, versao: str) -> tuple[str, bytes]:
    """Nome e conteúdo do .zip do recorte. Compartilhado entre as sessões; ``versao`` entra só na chave do cache."""
    recorte = montarRecorte(tipo, regiao, municipio)
    lotes = buscarLotes(tipo, regiao, municipio)
    limites = limitesDaApi(repositorio.carregarLimitesMunicipaisGdf())
    return f"{recorte.pasta}.zip", exportacaoQgis.gerarZip(recorte, lotes, limites, textoOrigem(versao))


def renderizar() -> None:
    try:
        regioes = repositorio.carregarRegioes()
    except ErroApi:
        mostrarErroDados()
        return
    if not regioes:
        st.error("Nenhuma região administrativa disponível.")
        return

    col1, col2 = st.columns([8, 3])
    with col2:
        paragrafoInformativo(
            "Gere um pacote para abrir no QGIS com os lotes da malha fundiária, coloridos pela categoria "
            "de tamanho, e os limites municipais. </br></br>"
            "O pacote é um arquivo .zip com as camadas em shapefile, os estilos, um projeto do QGIS e um "
            "README com o módulo fiscal e a descrição dos campos. O nome do proprietário não é exportado."
        )
    with col1:
        tipo = st.radio("Recorte", RECORTES, horizontal=True)
        regiao = municipio = None
        if tipo != RECORTE_ESTADO:
            regiao = st.selectbox("Região administrativa", regioes, format_func=exportacaoQgis.formatarTitulo)
        if tipo == RECORTE_MUNICIPIO:
            try:
                municipios = repositorio.carregarMunicipiosDaRegiao(regiao)
            except ErroApi:
                municipios = []
            if not municipios:
                st.warning("Nenhum município com lotes nesta região.")
                return
            municipio = st.selectbox("Município", municipios, format_func=exportacaoQgis.nomeOficial)
        if tipo == RECORTE_ESTADO:
            st.caption("O pacote do estado tem todos os lotes (cerca de 40 MB) e leva cerca de um minuto "
                       "para ficar pronto na primeira vez.")

        pedido = (tipo, regiao, municipio)
        if st.button("Gerar arquivos para o QGIS", icon=":material/map:", type="primary"):
            st.session_state[CHAVE_PEDIDO] = pedido
        if st.session_state.get(CHAVE_PEDIDO) != pedido:
            return
        try:
            with st.spinner("Montando o pacote..."):
                nomeArquivo, conteudo = gerarPacote(*pedido, repositorio.carregarVersaoDados())
        except ErroApi:
            mostrarErroDados()
            return
        except exportacaoQgis.ErroRecorte as erro:
            st.warning(str(erro))
            return
        tamanho = exportacaoQgis.formatarNumero(len(conteudo) / 1_000_000, 1)
        st.download_button(
            f"Baixar {nomeArquivo} ({tamanho} MB)", data=conteudo, file_name=nomeArquivo,
            mime="application/zip", icon=":material/download:", on_click="ignore",
        )
        st.caption("Descompacte o arquivo e abra o projeto .qgs no QGIS (Projeto > Abrir).")
