"""Testes de modules/paginaExportarQgis.py: dados da API, pacote em cache e botão de download."""
import io
import zipfile

import pytest
from streamlit.testing.v1 import AppTest

from modules import exportacaoQgis, navegacao
from modules import paginaExportarQgis as pe
from tests.conftest import criarLote, geojsonLotes


def conteudoDoZip(conteudo):
    with zipfile.ZipFile(io.BytesIO(conteudo)) as arquivoZip:
        return {nome: arquivoZip.read(nome) for nome in arquivoZip.namelist()}


def chamadasGeojson(miniserverSimulado):
    return [r.qs for r in miniserverSimulado.request_history if r.path.rstrip("/") == "/geojson"]


def test_lotesDaApiSoLevaAsColunasExportaveis():
    geojson = geojsonLotes([criarLote(nome_proprietario="Maria Joaquina de Amaral", nome_municipio="juazeiro_do_norte")])
    lotes = pe.lotesDaApi(geojson)
    assert set(lotes.columns) == {*pe.COLUNAS_API.values(), "chave", "geometry"}
    assert lotes["chave"].tolist() == ["juazeiro_do_norte"]
    assert lotes["nome_lote"].tolist() == ["Fazenda Teste"]


def test_pacoteDoMunicipioPelaApi(miniserverSimulado):
    nome, conteudo = pe.gerarPacote(pe.RECORTE_MUNICIPIO, "Regiao Teste", "fortaleza", "2026-09-30 10:00:00")
    assert nome == "fortaleza-shapefile.zip"
    arquivos = conteudoDoZip(conteudo)
    assert "fortaleza-shapefile/fortaleza.qgs" in arquivos
    readme = arquivos["fortaleza-shapefile/README.txt"].decode("utf-8")
    assert "Fortaleza (CE)" in readme and "carga de dados: 30/09/2026 07:00" in readme
    assert all(b"protegido pela LGPD" not in dados for dados in arquivos.values())
    # Os polígonos vêm sem simplificação.
    assert chamadasGeojson(miniserverSimulado) == [{"municipio": ["fortaleza"], "tolerance": ["0"]}]


def test_pacoteDoEstadoBuscaTodasAsRegioes(miniserverSimulado):
    nome, _ = pe.gerarPacote(pe.RECORTE_ESTADO, None, None, "")
    assert nome == "ceara-shapefile.zip"
    assert chamadasGeojson(miniserverSimulado) == [{"regiao": ["regiao teste"], "tolerance": ["0"]}]


def test_pacoteFicaEmCache(miniserverSimulado):
    pe.gerarPacote(pe.RECORTE_MUNICIPIO, "Regiao Teste", "fortaleza", "v1")
    pe.gerarPacote(pe.RECORTE_MUNICIPIO, "Regiao Teste", "fortaleza", "v1")
    assert len(chamadasGeojson(miniserverSimulado)) == 1
    pe.gerarPacote(pe.RECORTE_MUNICIPIO, "Regiao Teste", "fortaleza", "v2")
    assert len(chamadasGeojson(miniserverSimulado)) == 2


def test_regiaoForaDaTabelaViraErroDeRecorte():
    with pytest.raises(exportacaoQgis.ErroRecorte):
        pe.montarRecorte(pe.RECORTE_REGIAO, "Regiao Teste", None)


def test_botaoGeraOPacoteParaDownload(miniserverSimulado):
    at = AppTest.from_file("app.py", default_timeout=60)
    at.session_state[navegacao.CHAVE_SESSAO] = "exportarQgis"
    at.run()
    assert not chamadasGeojson(miniserverSimulado)  # nada é montado antes do clique
    [botao] = [b for b in at.button if b.label == "Gerar arquivos para o QGIS"]
    botao.click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state[pe.CHAVE_PEDIDO] == (pe.RECORTE_MUNICIPIO, "Regiao Teste", "fortaleza")
    downloads = at.get("download_button")
    assert len(downloads) == 1
    assert "fortaleza-shapefile.zip" in downloads[0].proto.label


def test_formatarVersao():
    assert pe.formatarVersao("2026-10-27 14:55:40.500561+00:00") == "27/10/2026 11:55"
    assert pe.formatarVersao("") == "não informada"
    assert pe.formatarVersao("carga-7") == "carga-7"
