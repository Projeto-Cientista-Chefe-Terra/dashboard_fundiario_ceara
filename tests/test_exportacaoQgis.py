"""Testes de modules/exportacaoQgis.py: recortes, camadas, estilos, projeto e README do pacote do QGIS."""
import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import pytest
import shapely

from modules import exportacaoQgis as eq

SALITRE = shapely.box(-40.4, -7.3, -40.2, -7.1)
CAMPOS_SALES = shapely.box(-40.6, -7.3, -40.4, -7.1)
CSV_REGIOES = Path(__file__).resolve().parents[2] / "terraGeoDataMiniServer/datasets/regioes_municipios_modulos_fiscais_ceara.csv"


def criarLimites():
    return gpd.GeoDataFrame(
        {"chave": ["salitre", "campos_sales"], "area_km2": ["806.253", "1082.8"]},
        geometry=[SALITRE, CAMPOS_SALES], crs=4674,
    )


def criarLotes(**extras):
    return gpd.GeoDataFrame(
        {
            "chave": ["salitre", "salitre", "campos_sales", "salitre"],
            "lote_id": [3, 1, 2, 4],
            "nome_lote": ["Sítio São José", "", "Fazenda Açude", "Lote Fora"],
            "dt_criacao": ["2024-07-10", "", "2023-11-21 15:30:12", None],
            "num_incra": ["1234567890123", "", None, "9"],
            "num_lote": ["0217", "4186", "12", "13"],
            "area_ha": ["10.123456", "300", "2000", "1"],
            "sit_jurid": ["Posse por Simples Ocupação"] * 4,
            "categoria": ["Pequena Propriedade < 1 MF", "Média Propriedade", "Grande Propriedade", "Pequena Propriedade < 1 MF"],
            **extras,
        },
        geometry=[
            shapely.box(-40.35, -7.25, -40.34, -7.24),
            shapely.box(-40.30, -7.20, -40.29, -7.19),
            shapely.box(-40.50, -7.20, -40.49, -7.19),
            shapely.box(-40.55, -7.25, -40.54, -7.24),  # de Salitre, mas dentro de Campos Sales
        ],
        crs=4674,
    )


def gravar(tmp_path, recorte, lotes=None, origem="  Dados de teste."):
    pasta = tmp_path / recorte.pasta
    arquivos = eq.gravarPacote(pasta, recorte, criarLotes() if lotes is None else lotes, criarLimites(), origem)
    return pasta, arquivos


def lerProjeto(pasta, recorte):
    return ET.parse(pasta / f"{recorte.chave}.qgs").getroot()


def test_normalizacaoEFormatacao():
    assert eq.normalizarNome("São Gonçalo do Amarante") == "sao_goncalo_do_amarante"
    assert eq.normalizarNome("LITORAL OESTE - VALE DO CURU") == "litoral_oeste_vale_do_curu"
    assert eq.formatarTitulo("SERTÃO DE CRATEÚS") == "Sertão de Crateús"
    assert eq.formatarNumero(82128.37, 2) == "82.128,37"
    assert eq.quantidadeDeLotes(1) == "1 lote"
    assert eq.quantidadeDeLotes(4839) == "4.839 lotes"
    assert eq.nomeOficial("juazeiro_do_norte") == "Juazeiro do Norte"


def test_tabelaTemOs184MunicipiosEAs14Regioes():
    assert len(eq.MUNICIPIOS_POR_CHAVE) == 184
    assert len(eq.REGIOES_POR_CHAVE) == 14
    assert eq.MUNICIPIOS_POR_CHAVE["salitre"] == eq.Municipio("2311959", "Salitre", "Cariri", 70.0)


@pytest.mark.skipif(not CSV_REGIOES.exists(), reason="CSV do miniserver indisponível")
def test_tabelaConfereComOCsvDoMiniserver():
    csv = pd.read_csv(CSV_REGIOES, dtype=str)
    for linha in csv.itertuples():
        municipio = eq.MUNICIPIOS_POR_CHAVE[eq.normalizarNome(linha.nome_municipio)]
        assert municipio.moduloFiscal == float(linha.modulo_fiscal), linha.nome_municipio
        assert eq.normalizarNome(municipio.regiao) == eq.normalizarNome(linha.regiao_administrativa)
    assert len(csv) == len(eq.MUNICIPIOS_POR_CHAVE)


def test_recortes():
    municipio = eq.recorteMunicipio("Juazeiro do Norte")
    assert (municipio.chave, municipio.nome, municipio.pasta) == ("juazeiro_do_norte", "Juazeiro do Norte", "juazeiro_do_norte-shapefile")
    regiao = eq.recorteRegiao("LITORAL OESTE - VALE DO CURU")
    assert (regiao.chave, regiao.nome) == ("litoral_oeste_vale_do_curu", "Litoral Oeste - Vale do Curu")
    assert len(eq.recorteRegiao("cariri").chavesMunicipios()) == 29
    assert len(eq.recorteEstado().chavesMunicipios()) == 184
    assert eq.recorteEstado().titulo == "Estado do Ceará"


def test_nomeDesconhecidoSugereOParecido():
    with pytest.raises(eq.ErroRecorte, match="Você quis dizer: salitre"):
        eq.recorteMunicipio("salitr")
    with pytest.raises(eq.ErroRecorte, match="não encontrada"):
        eq.recorteRegiao("sertao_crateus")


def test_pacoteDoMunicipio(tmp_path):
    recorte = eq.recorteMunicipio("salitre")
    pasta, arquivos = gravar(tmp_path, recorte)
    assert {a.name for a in arquivos} == set(recorte.arquivos())

    info = pyogrio.read_info(pasta / "salitre_lotes.shp")
    assert list(info["fields"]) == [
        "lote_id", "nome_lote", "dt_criacao", "num_incra", "num_lote", "area_ha",
        "mod_fiscal", "sit_jurid", "municipio", "reg_adm", "categoria",
    ]
    assert info["dtypes"][2] == "datetime64[D]"  # campo Date do DBF
    assert info["encoding"] == "UTF-8"
    lotes = gpd.read_file(pasta / "salitre_lotes.shp")
    assert lotes["lote_id"].tolist() == [1, 3, 4]
    assert lotes["municipio"].unique().tolist() == ["Salitre"]
    assert lotes["mod_fiscal"].unique().tolist() == [70.0]
    assert lotes.loc[lotes["lote_id"] == 3, "nome_lote"].item() == "Sítio São José"
    assert pd.isna(lotes.loc[lotes["lote_id"] == 1, "nome_lote"].item())
    assert lotes.loc[lotes["lote_id"] == 3, "area_ha"].item() == pytest.approx(10.1235)
    assert lotes.crs.to_epsg() == eq.EPSG_SAIDA

    limites = gpd.read_file(pasta / "salitre_municipio.shp")
    assert limites[["cd_mun", "municipio", "reg_adm", "n_lotes"]].to_dict("records") == [
        {"cd_mun": "2311959", "municipio": "Salitre", "reg_adm": "Cariri", "n_lotes": 3}
    ]


def test_nomeDoProprietarioNuncaEExportado(tmp_path):
    lotes = criarLotes(nome_proprietario=["Maria Joaquina de Amaral"] * 4, id_proprietario=["abc"] * 4)
    pasta, arquivos = gravar(tmp_path, eq.recorteMunicipio("salitre"), lotes=lotes)
    assert "nome_proprietario" not in pyogrio.read_info(pasta / "salitre_lotes.shp")["fields"]
    for arquivo in arquivos:
        assert b"Maria Joaquina" not in arquivo.read_bytes(), arquivo.name


def test_projetoDoMunicipio(tmp_path):
    recorte = eq.recorteMunicipio("salitre")
    pasta, _ = gravar(tmp_path, recorte)
    raiz = lerProjeto(pasta, recorte)
    camadas = raiz.findall("projectlayers/maplayer")
    assert [c.findtext("datasource") for c in camadas] == ["./salitre_municipio.shp", "./salitre_lotes.shp"]
    assert raiz.find("properties/Paths/Absolute").text == "false"
    assert raiz.find("properties/SpatialRefSys/ProjectionsEnabled").text == "1"
    extensao = raiz.find("ProjectViewSettings/DefaultViewExtent")
    assert float(extensao.get("xmin")) < -40.35 and float(extensao.get("xmax")) > -40.2

    renderer = camadas[1].find("renderer-v2")
    assert renderer.get("attr") == "categoria"
    categorias = renderer.findall("categories/category")
    assert [c.get("value") for c in categorias] == ["Pequena Propriedade < 1 MF", "Média Propriedade"]
    assert categorias[0].get("label") == "Menor que 1 MF (menos de 70 ha)"
    assert categorias[1].get("label") == "Média: mais de 4 a 15 MF (mais de 280 a 1.050 ha)"
    assert camadas[0].find("labeling") is None

    estilo = ET.parse(pasta / "salitre_lotes.qml").getroot()
    assert [c.get("value") for c in estilo.findall("renderer-v2/categories/category")] == ["Pequena Propriedade < 1 MF", "Média Propriedade"]


def test_pacoteDaRegiaoTemRotulosEModuloPorMunicipio(tmp_path):
    recorte = eq.recorteRegiao("cariri")
    pasta, arquivos = gravar(tmp_path, recorte)
    assert "cariri_municipios.shp" in {a.name for a in arquivos}
    assert len(gpd.read_file(pasta / "cariri_lotes.shp")) == 4

    camadas = lerProjeto(pasta, recorte).findall("projectlayers/maplayer")
    assert camadas[0].get("labelsEnabled") == "1"
    assert camadas[0].find("labeling/settings/text-style").get("fieldName") == "municipio"
    rotulos = [c.get("label") for c in camadas[1].findall("renderer-v2/categories/category")]
    assert rotulos == ["Menor que 1 MF", "Média: mais de 4 a 15 MF", "Grande: mais de 15 MF"]
    assert ET.parse(pasta / "cariri_municipios.qml").getroot().get("labelsEnabled") == "1"

    readme = (pasta / "README.txt").read_text(encoding="utf-8")
    assert "Região Administrativa Cariri (CE)" in readme
    assert "O módulo fiscal varia por município" in readme
    assert "Campos Sales" in readme and "Salitre" in readme


def test_readmeDoMunicipio(tmp_path):
    pasta, _ = gravar(tmp_path, eq.recorteMunicipio("salitre"))
    readme = (pasta / "README.txt").read_text(encoding="utf-8")
    assert "1 módulo fiscal (MF) equivale a 70 hectares" in readme
    assert "de 70 a 280 ha" in readme
    assert "1 lote (1 ha) tem o ponto interno fora do contorno" in readme
    assert "a data de criação está vazia em 2 lotes" in readme
    assert "Dados de teste." in readme
    assert "O nome do proprietário não é exportado." in readme


def test_lotesSemGeometriaOuForaDoRecorteSaem(tmp_path):
    lotes = criarLotes()
    lotes.loc[0, "geometry"] = shapely.Polygon()
    lotes.loc[1, "geometry"] = shapely.Polygon([(-40.3, -7.2), (-40.3, -7.2), (-40.29, -7.19), (-40.3, -7.2)])  # área zero
    pasta, _ = gravar(tmp_path, eq.recorteMunicipio("salitre"), lotes=lotes)
    assert gpd.read_file(pasta / "salitre_lotes.shp")["lote_id"].tolist() == [4]


def test_recorteSemLotes(tmp_path):
    with pytest.raises(eq.ErroRecorte, match="não há lotes"):
        gravar(tmp_path, eq.recorteMunicipio("fortaleza"))


def test_gerarZip():
    recorte = eq.recorteMunicipio("salitre")
    conteudo = eq.gerarZip(recorte, criarLotes(), criarLimites(), "  Dados de teste.")
    with zipfile.ZipFile(io.BytesIO(conteudo)) as arquivoZip:
        nomes = arquivoZip.namelist()
    assert all(nome.startswith("salitre-shapefile/") for nome in nomes)
    assert {"salitre-shapefile/salitre.qgs", "salitre-shapefile/README.txt", "salitre-shapefile/salitre_lotes.shp"} <= set(nomes)
