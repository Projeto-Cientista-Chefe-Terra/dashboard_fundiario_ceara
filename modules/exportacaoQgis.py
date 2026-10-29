# modules/exportacaoQgis.py
"""Pacote de arquivos para abrir os lotes da malha fundiária no QGIS.

Três recortes: um município, uma região administrativa ou o estado inteiro. O
pacote traz duas camadas em shapefile (os lotes, coloridos pela categoria de
tamanho, e os limites municipais), um estilo .qml para cada uma, um projeto do
QGIS (.qgs) que abre as duas já estilizadas e um README.txt.

O módulo não sabe de onde vêm os dados nem chama ``st.*``. Quem chama entrega
dois GeoDataFrames com a coluna ``chave`` (o nome do município sem acento, em
minúsculas e com "_", como nas tabelas do miniserver):

- lotes: ``geometry`` e, se houver, ``lote_id``, ``nome_lote``, ``dt_criacao``,
  ``num_incra``, ``num_lote``, ``area_ha``, ``sit_jurid`` e ``categoria``;
- limites: ``geometry`` e, se houver, ``area_km2``.

Nome oficial, região e módulo fiscal saem da tabela ``MUNICIPIOS_CEARA``. Só as
colunas de ``COLUNAS_LOTES`` vão para o pacote, então o nome do proprietário
nunca é exportado, mesmo que venha nos dados.

O dashboard monta os dados pela API do miniserver (``paginaExportarQgis``) e o
script ``scripts/gerarPacoteQgis.py``, pelos CSVs do miniserver.
"""

import difflib
import io
import re
import tempfile
import unicodedata
import uuid
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NamedTuple

import geopandas as gpd
import pandas as pd
import pyarrow as pa
import shapely
from pyproj import CRS

from modules.classificacao import CATEGORIAS, SEM_CLASSIFICACAO
from public.cores import CORES

EPSG_SAIDA = 4674  # SIRGAS 2000 geográfico
EPSG_METRICO = 31984  # SIRGAS 2000 / UTM 24S, para medir áreas e distâncias
AREA_MINIMA_M2 = 1e-6  # abaixo de 1 mm², a área é zero com erro de arredondamento
VERSAO_QGIS = "3.28.0-Firenze"

NIVEL_MUNICIPIO = "municipio"
NIVEL_REGIAO = "regiao"
NIVEL_ESTADO = "estado"

# Mesmas cores do dashboard. "Sem Classificação" não tem cor no mapa do dashboard.
CORES_CATEGORIAS = {**{categoria: CORES[categoria] for categoria in CATEGORIAS}, SEM_CLASSIFICACAO: "#cccccc"}
NOMES_CORES = {
    "#ffb3b5": "rosa", "#e2c288": "bege", "#abd28c": "verde-claro", "#6bdabc": "verde-água", "#cccccc": "cinza",
}

# Campos de cada camada, na ordem do shapefile, com a descrição usada no README.
COLUNAS_LOTES = {
    "lote_id": "identificador do lote na base",
    "nome_lote": "nome do lote (imóvel)",
    "dt_criacao": "data de criação do lote",
    "num_incra": "número do INCRA",
    "num_lote": "número do lote",
    "area_ha": "área em hectares, com 4 casas decimais",
    "mod_fiscal": "módulo fiscal do município, em hectares",
    "sit_jurid": "situação jurídica",
    "municipio": "município",
    "reg_adm": "região administrativa",
    "categoria": "categoria pelo tamanho em módulos fiscais",
}
COLUNAS_LIMITES = {
    "cd_mun": "código IBGE",
    "municipio": "nome",
    "reg_adm": "região administrativa",
    "area_km2": "área oficial em km²",
    "mod_fiscal": "tamanho do módulo fiscal, em hectares",
    "n_lotes": "quantidade de lotes neste pacote",
}
COLUNAS_TEXTO_LOTES = ["nome_lote", "num_incra", "num_lote", "sit_jurid", "categoria"]
EXTENSOES_SHAPEFILE = (".shp", ".shx", ".dbf", ".prj", ".cpg", ".qml")
CONECTIVOS = {"de", "do", "da", "dos", "das", "e"}

# Os 184 municípios do Ceará pelo código IBGE: nome oficial (API de localidades
# do IBGE), região administrativa e módulo fiscal em hectares (tabela do INCRA
# usada pelo miniserver, regioes_municipios_modulos_fiscais_ceara.csv). A API do
# miniserver não expõe essa tabela e só lista municípios que têm lotes.
MUNICIPIOS_CEARA = {
    "2300101": ("Abaiara", "Cariri", 45),
    "2300150": ("Acarape", "Maciço do Baturité", 35),
    "2300200": ("Acaraú", "Litoral Norte", 55),
    "2300309": ("Acopiara", "Centro Sul", 40),
    "2300408": ("Aiuaba", "Sertão dos Inhamuns", 90),
    "2300507": ("Alcântaras", "Sertão de Sobral", 40),
    "2300606": ("Altaneira", "Cariri", 50),
    "2300705": ("Alto Santo", "Vale do Jaguaribe", 55),
    "2300754": ("Amontada", "Litoral Oeste - Vale do Curu", 50),
    "2300804": ("Antonina do Norte", "Cariri", 50),
    "2300903": ("Apuiarés", "Litoral Oeste - Vale do Curu", 50),
    "2301000": ("Aquiraz", "Grande Fortaleza", 10),
    "2301109": ("Aracati", "Litoral Leste", 45),
    "2301208": ("Aracoiaba", "Maciço do Baturité", 40),
    "2301257": ("Ararendá", "Sertão de Crateús", 70),
    "2301307": ("Araripe", "Cariri", 65),
    "2301406": ("Aratuba", "Maciço do Baturité", 20),
    "2301505": ("Arneiroz", "Sertão dos Inhamuns", 90),
    "2301604": ("Assaré", "Cariri", 50),
    "2301703": ("Aurora", "Cariri", 45),
    "2301802": ("Baixio", "Centro Sul", 40),
    "2301851": ("Banabuiú", "Sertão Central", 50),
    "2301901": ("Barbalha", "Cariri", 26),
    "2301950": ("Barreira", "Maciço do Baturité", 35),
    "2302008": ("Barro", "Cariri", 45),
    "2302057": ("Barroquinha", "Litoral Norte", 55),
    "2302107": ("Baturité", "Maciço do Baturité", 40),
    "2302206": ("Beberibe", "Litoral Leste", 28),
    "2302305": ("Bela Cruz", "Litoral Norte", 40),
    "2302404": ("Boa Viagem", "Sertão de Canindé", 50),
    "2302503": ("Brejo Santo", "Cariri", 45),
    "2302602": ("Camocim", "Litoral Norte", 55),
    "2302701": ("Campos Sales", "Cariri", 70),
    "2302800": ("Canindé", "Sertão de Canindé", 50),
    "2302909": ("Capistrano", "Maciço do Baturité", 45),
    "2303006": ("Caridade", "Sertão de Canindé", 50),
    "2303105": ("Cariré", "Sertão de Sobral", 55),
    "2303204": ("Caririaçu", "Cariri", 45),
    "2303303": ("Cariús", "Centro Sul", 40),
    "2303402": ("Carnaubal", "Serra da Ibiapaba", 50),
    "2303501": ("Cascavel", "Grande Fortaleza", 28),
    "2303600": ("Catarina", "Centro Sul", 90),
    "2303659": ("Catunda", "Sertão de Crateús", 55),
    "2303709": ("Caucaia", "Grande Fortaleza", 15),
    "2303808": ("Cedro", "Centro Sul", 40),
    "2303907": ("Chaval", "Litoral Norte", 55),
    "2303931": ("Choró", "Sertão Central", 50),
    "2303956": ("Chorozinho", "Grande Fortaleza", 16),
    "2304004": ("Coreaú", "Sertão de Sobral", 55),
    "2304103": ("Crateús", "Sertão de Crateús", 80),
    "2304202": ("Crato", "Cariri", 26),
    "2304236": ("Croatá", "Serra da Ibiapaba", 45),
    "2304251": ("Cruz", "Litoral Norte", 55),
    "2304269": ("Deputado Irapuan Pinheiro", "Sertão Central", 55),
    "2304277": ("Ereré", "Vale do Jaguaribe", 55),
    "2304285": ("Eusébio", "Grande Fortaleza", 10),
    "2304301": ("Farias Brito", "Cariri", 50),
    "2304350": ("Forquilha", "Sertão de Sobral", 50),
    "2304400": ("Fortaleza", "Grande Fortaleza", 5),
    "2304459": ("Fortim", "Litoral Leste", 45),
    "2304509": ("Frecheirinha", "Sertão de Sobral", 50),
    "2304608": ("General Sampaio", "Litoral Oeste - Vale do Curu", 50),
    "2304657": ("Graça", "Sertão de Sobral", 40),
    "2304707": ("Granja", "Litoral Norte", 55),
    "2304806": ("Granjeiro", "Cariri", 45),
    "2304905": ("Groaíras", "Sertão de Sobral", 55),
    "2304954": ("Guaiúba", "Grande Fortaleza", 15),
    "2305001": ("Guaraciaba do Norte", "Serra da Ibiapaba", 45),
    "2305100": ("Guaramiranga", "Maciço do Baturité", 20),
    "2305209": ("Hidrolândia", "Sertão de Crateús", 50),
    "2305233": ("Horizonte", "Grande Fortaleza", 16),
    "2305266": ("Ibaretama", "Sertão Central", 50),
    "2305308": ("Ibiapina", "Serra da Ibiapaba", 45),
    "2305332": ("Ibicuitinga", "Sertão Central", 55),
    "2305357": ("Icapuí", "Litoral Leste", 45),
    "2305407": ("Icó", "Centro Sul", 40),
    "2305506": ("Iguatu", "Centro Sul", 40),
    "2305605": ("Independência", "Sertão de Crateús", 80),
    "2305654": ("Ipaporanga", "Sertão de Crateús", 70),
    "2305704": ("Ipaumirim", "Centro Sul", 40),
    "2305803": ("Ipu", "Serra da Ibiapaba", 50),
    "2305902": ("Ipueiras", "Sertão de Crateús", 70),
    "2306009": ("Iracema", "Vale do Jaguaribe", 60),
    "2306108": ("Irauçuba", "Litoral Oeste - Vale do Curu", 55),
    "2306207": ("Itaiçaba", "Litoral Leste", 55),
    "2306256": ("Itaitinga", "Grande Fortaleza", 15),
    "2306306": ("Itapajé", "Litoral Oeste - Vale do Curu", 45),
    "2306405": ("Itapipoca", "Litoral Oeste - Vale do Curu", 50),
    "2306504": ("Itapiúna", "Maciço do Baturité", 45),
    "2306553": ("Itarema", "Litoral Norte", 55),
    "2306603": ("Itatira", "Sertão de Canindé", 50),
    "2306702": ("Jaguaretama", "Vale do Jaguaribe", 55),
    "2306801": ("Jaguaribara", "Vale do Jaguaribe", 55),
    "2306900": ("Jaguaribe", "Vale do Jaguaribe", 55),
    "2307007": ("Jaguaruana", "Litoral Leste", 55),
    "2307106": ("Jardim", "Cariri", 26),
    "2307205": ("Jati", "Cariri", 45),
    "2307254": ("Jijoca de Jericoacoara", "Litoral Norte", 55),
    "2307304": ("Juazeiro do Norte", "Cariri", 26),
    "2307403": ("Jucás", "Centro Sul", 40),
    "2307502": ("Lavras da Mangabeira", "Cariri", 40),
    "2307601": ("Limoeiro do Norte", "Vale do Jaguaribe", 55),
    "2307635": ("Madalena", "Sertão de Canindé", 50),
    "2307650": ("Maracanaú", "Grande Fortaleza", 15),
    "2307700": ("Maranguape", "Grande Fortaleza", 15),
    "2307809": ("Marco", "Litoral Norte", 55),
    "2307908": ("Martinópole", "Litoral Norte", 55),
    "2308005": ("Massapê", "Sertão de Sobral", 50),
    "2308104": ("Mauriti", "Cariri", 45),
    "2308203": ("Meruoca", "Sertão de Sobral", 40),
    "2308302": ("Milagres", "Cariri", 45),
    "2308351": ("Milhã", "Sertão Central", 55),
    "2308377": ("Miraíma", "Litoral Oeste - Vale do Curu", 50),
    "2308401": ("Missão Velha", "Cariri", 26),
    "2308500": ("Mombaça", "Sertão Central", 40),
    "2308609": ("Monsenhor Tabosa", "Sertão de Crateús", 80),
    "2308708": ("Morada Nova", "Vale do Jaguaribe", 55),
    "2308807": ("Moraújo", "Sertão de Sobral", 55),
    "2308906": ("Morrinhos", "Litoral Norte", 65),
    "2309003": ("Mucambo", "Sertão de Sobral", 55),
    "2309102": ("Mulungu", "Maciço do Baturité", 20),
    "2309201": ("Nova Olinda", "Cariri", 55),
    "2309300": ("Nova Russas", "Sertão de Crateús", 70),
    "2309409": ("Novo Oriente", "Sertão de Crateús", 80),
    "2309458": ("Ocara", "Maciço do Baturité", 40),
    "2309508": ("Orós", "Centro Sul", 40),
    "2309607": ("Pacajus", "Grande Fortaleza", 16),
    "2309706": ("Pacatuba", "Grande Fortaleza", 15),
    "2309805": ("Pacoti", "Maciço do Baturité", 20),
    "2309904": ("Pacujá", "Sertão de Sobral", 55),
    "2310001": ("Palhano", "Vale do Jaguaribe", 55),
    "2310100": ("Palmácia", "Maciço do Baturité", 20),
    "2310209": ("Paracuru", "Grande Fortaleza", 45),
    "2310258": ("Paraipaba", "Grande Fortaleza", 45),
    "2310308": ("Parambu", "Sertão dos Inhamuns", 90),
    "2310407": ("Paramoti", "Sertão de Canindé", 50),
    "2310506": ("Pedra Branca", "Sertão Central", 50),
    "2310605": ("Penaforte", "Cariri", 45),
    "2310704": ("Pentecoste", "Litoral Oeste - Vale do Curu", 50),
    "2310803": ("Pereiro", "Vale do Jaguaribe", 55),
    "2310852": ("Pindoretama", "Grande Fortaleza", 28),
    "2310902": ("Piquet Carneiro", "Sertão Central", 50),
    "2310951": ("Pires Ferreira", "Sertão de Sobral", 50),
    "2311009": ("Poranga", "Sertão de Crateús", 70),
    "2311108": ("Porteiras", "Cariri", 45),
    "2311207": ("Potengi", "Cariri", 60),
    "2311231": ("Potiretama", "Vale do Jaguaribe", 60),
    "2311264": ("Quiterianópolis", "Sertão dos Inhamuns", 80),
    "2311306": ("Quixadá", "Sertão Central", 50),
    "2311355": ("Quixelô", "Centro Sul", 40),
    "2311405": ("Quixeramobim", "Sertão Central", 50),
    "2311504": ("Quixeré", "Vale do Jaguaribe", 55),
    "2311603": ("Redenção", "Maciço do Baturité", 35),
    "2311702": ("Reriutaba", "Sertão de Sobral", 55),
    "2311801": ("Russas", "Vale do Jaguaribe", 55),
    "2311900": ("Saboeiro", "Centro Sul", 90),
    "2311959": ("Salitre", "Cariri", 70),
    "2312007": ("Santana do Acaraú", "Sertão de Sobral", 65),
    "2312106": ("Santana do Cariri", "Cariri", 55),
    "2312205": ("Santa Quitéria", "Sertão de Crateús", 55),
    "2312304": ("São Benedito", "Serra da Ibiapaba", 40),
    "2312403": ("São Gonçalo do Amarante", "Grande Fortaleza", 50),
    "2312502": ("São João do Jaguaribe", "Vale do Jaguaribe", 55),
    "2312601": ("São Luís do Curu", "Grande Fortaleza", 50),
    "2312700": ("Senador Pompeu", "Sertão Central", 50),
    "2312809": ("Senador Sá", "Sertão de Sobral", 65),
    "2312908": ("Sobral", "Sertão de Sobral", 50),
    "2313005": ("Solonópole", "Sertão Central", 55),
    "2313104": ("Tabuleiro do Norte", "Vale do Jaguaribe", 55),
    "2313203": ("Tamboril", "Sertão de Crateús", 80),
    "2313252": ("Tarrafas", "Cariri", 50),
    "2313302": ("Tauá", "Sertão dos Inhamuns", 90),
    "2313351": ("Tejuçuoca", "Litoral Oeste - Vale do Curu", 45),
    "2313401": ("Tianguá", "Serra da Ibiapaba", 45),
    "2313500": ("Trairi", "Grande Fortaleza", 50),
    "2313559": ("Tururu", "Litoral Oeste - Vale do Curu", 35),
    "2313609": ("Ubajara", "Serra da Ibiapaba", 50),
    "2313708": ("Umari", "Centro Sul", 40),
    "2313757": ("Umirim", "Litoral Oeste - Vale do Curu", 35),
    "2313807": ("Uruburetama", "Litoral Oeste - Vale do Curu", 35),
    "2313906": ("Uruoca", "Litoral Norte", 65),
    "2313955": ("Varjota", "Sertão de Sobral", 55),
    "2314003": ("Várzea Alegre", "Cariri", 50),
    "2314102": ("Viçosa do Ceará", "Serra da Ibiapaba", 50),
}


class ErroRecorte(ValueError):
    """Recorte inexistente ou sem lotes."""


class Municipio(NamedTuple):
    codigo: str
    nome: str
    regiao: str
    moduloFiscal: float


def normalizarNome(texto: str) -> str:
    """'Juazeiro do Norte' ou 'JUAZEIRO DO NORTE' viram 'juazeiro_do_norte'."""
    semAcento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return "_".join(re.sub(r"[^a-z0-9]+", " ", semAcento.lower()).split())


def formatarTitulo(texto: str) -> str:
    """'SERTÃO DE CRATEÚS' vira 'Sertão de Crateús'."""
    palavras = texto.lower().split()
    return " ".join(
        p if (i > 0 and p in CONECTIVOS) else p[:1].upper() + p[1:] for i, p in enumerate(palavras)
    )


def contar(quantidade: int, singular: str, plural: str) -> str:
    """'1 lote' ou '4.839 lotes'."""
    return f"{formatarNumero(quantidade)} {singular if quantidade == 1 else plural}"


def quantidadeDeLotes(quantidade: int) -> str:
    return contar(quantidade, "lote", "lotes")


def formatarNumero(valor: float, casas: int = 0) -> str:
    """Número no padrão brasileiro: 82128.37 vira '82.128,37'."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


MUNICIPIOS_POR_CHAVE = {
    normalizarNome(nome): Municipio(codigo, nome, regiao, float(moduloFiscal))
    for codigo, (nome, regiao, moduloFiscal) in MUNICIPIOS_CEARA.items()
}
REGIOES_POR_CHAVE = {normalizarNome(m.regiao): m.regiao for m in MUNICIPIOS_POR_CHAVE.values()}


def nomeOficial(chave: str) -> str:
    """Nome com acentos de um município, a partir da chave usada no miniserver."""
    municipio = MUNICIPIOS_POR_CHAVE.get(normalizarNome(chave))
    return municipio.nome if municipio else formatarTitulo(chave.replace("_", " "))


# ==================== Recortes ====================

@dataclass(frozen=True)
class Recorte:
    nivel: str
    chave: str
    nome: str

    @property
    def titulo(self) -> str:
        if self.nivel == NIVEL_MUNICIPIO:
            return f"{self.nome} (CE)"
        if self.nivel == NIVEL_REGIAO:
            return f"Região Administrativa {self.nome} (CE)"
        return "Estado do Ceará"

    @property
    def pasta(self) -> str:
        return f"{self.chave}-shapefile"

    @property
    def arquivoLimites(self) -> str:
        return f"{self.chave}_municipio" if self.nivel == NIVEL_MUNICIPIO else f"{self.chave}_municipios"

    @property
    def arquivoLotes(self) -> str:
        return f"{self.chave}_lotes"

    def chavesMunicipios(self) -> list[str]:
        if self.nivel == NIVEL_MUNICIPIO:
            return [self.chave]
        if self.nivel == NIVEL_REGIAO:
            return [c for c, m in MUNICIPIOS_POR_CHAVE.items() if normalizarNome(m.regiao) == self.chave]
        return list(MUNICIPIOS_POR_CHAVE)

    def arquivos(self) -> list[str]:
        """Nomes de todos os arquivos que o pacote deste recorte pode ter."""
        nomes = [f"{base}{ext}" for base in (self.arquivoLimites, self.arquivoLotes) for ext in EXTENSOES_SHAPEFILE]
        return nomes + [f"{self.chave}.qgs", "README.txt"]


def _naoEncontrado(mensagem: str, nome: str, opcoes) -> ErroRecorte:
    parecidos = difflib.get_close_matches(normalizarNome(nome), list(opcoes), n=3)
    dica = f" Você quis dizer: {', '.join(parecidos)}?" if parecidos else ""
    return ErroRecorte(f"{mensagem}.{dica}")


def recorteMunicipio(nome: str) -> Recorte:
    chave = normalizarNome(nome)
    if chave not in MUNICIPIOS_POR_CHAVE:
        raise _naoEncontrado(f"Município '{nome}' não encontrado", nome, MUNICIPIOS_POR_CHAVE)
    return Recorte(NIVEL_MUNICIPIO, chave, MUNICIPIOS_POR_CHAVE[chave].nome)


def recorteRegiao(nome: str) -> Recorte:
    chave = normalizarNome(nome)
    if chave not in REGIOES_POR_CHAVE:
        raise _naoEncontrado(f"Região administrativa '{nome}' não encontrada", nome, REGIOES_POR_CHAVE)
    return Recorte(NIVEL_REGIAO, chave, REGIOES_POR_CHAVE[chave])


def recorteEstado() -> Recorte:
    return Recorte(NIVEL_ESTADO, "ceara", "Ceará")


# ==================== Camadas ====================

def prepararCamadas(recorte: Recorte, lotes: gpd.GeoDataFrame, limites: gpd.GeoDataFrame):
    """Camadas de lotes e de limites do recorte, só com as colunas exportáveis."""
    chaves = recorte.chavesMunicipios()
    lotes = lotes[lotes["chave"].isin(chaves)].to_crs(EPSG_METRICO)
    # Lotes vazios ou degenerados (alguns vêm assim da base, com área de 1e-11 a
    # 1e-9 m²) não têm o que desenhar. A API do miniserver já os descarta; aqui, os CSVs também.
    # A área é 0 para geometria vazia e NaN para ausente, e as duas ficam de fora.
    lotes = lotes[shapely.area(lotes.geometry.to_numpy()) >= AREA_MINIMA_M2].reset_index(drop=True)
    if lotes.empty:
        raise ErroRecorte(f"{recorte.titulo}: não há lotes na malha fundiária.")
    limites = limites[limites["chave"].isin(chaves)].reset_index(drop=True)
    if limites.empty:
        raise ErroRecorte(f"{recorte.titulo}: não há limites municipais.")

    municipios = lotes["chave"].map(MUNICIPIOS_POR_CHAVE)
    dados = {coluna: lotes[coluna] for coluna in ("lote_id", "nome_lote", "num_incra", "num_lote") if coluna in lotes}
    if "dt_criacao" in lotes:
        # O campo Date do DBF não guarda hora; a hora, quando existe, é descartada.
        dados["dt_criacao"] = pd.to_datetime(lotes["dt_criacao"], format="ISO8601", errors="coerce").dt.normalize()
    if "area_ha" in lotes:
        dados["area_ha"] = pd.to_numeric(lotes["area_ha"], errors="coerce").round(4)
    dados["mod_fiscal"] = municipios.map(lambda m: m.moduloFiscal)
    dados["sit_jurid"] = lotes.get("sit_jurid")
    dados["municipio"] = municipios.map(lambda m: m.nome)
    dados["reg_adm"] = municipios.map(lambda m: m.regiao)
    dados["categoria"] = lotes.get("categoria")
    colunas = [c for c in COLUNAS_LOTES if c in dados and dados[c] is not None]
    camadaLotes = gpd.GeoDataFrame({c: dados[c] for c in colunas}, geometry=lotes.geometry.to_numpy(), crs=lotes.crs)
    textos = [c for c in COLUNAS_TEXTO_LOTES if c in camadaLotes]
    camadaLotes[textos] = camadaLotes[textos].replace({"": None})
    ordem = ["lote_id"] if "lote_id" in camadaLotes else ["municipio", "num_lote"]
    camadaLotes = camadaLotes.sort_values(ordem).reset_index(drop=True)

    municipiosLimites = limites["chave"].map(MUNICIPIOS_POR_CHAVE)
    quantidade = lotes["chave"].value_counts()
    camadaLimites = gpd.GeoDataFrame(
        {
            "cd_mun": municipiosLimites.map(lambda m: m.codigo),
            "municipio": municipiosLimites.map(lambda m: m.nome),
            "reg_adm": municipiosLimites.map(lambda m: m.regiao),
            **({"area_km2": pd.to_numeric(limites["area_km2"])} if "area_km2" in limites else {}),
            "mod_fiscal": municipiosLimites.map(lambda m: m.moduloFiscal),
            "n_lotes": limites["chave"].map(quantidade).fillna(0).astype("int64"),
        },
        geometry=limites.geometry.to_numpy(),
        crs=limites.crs,
    ).sort_values("municipio").reset_index(drop=True)
    return camadaLotes, camadaLimites.to_crs(EPSG_METRICO)


def lotesForaDoMunicipio(camadaLotes: gpd.GeoDataFrame, camadaLimites: gpd.GeoDataFrame) -> pd.Series:
    """Distância, em metros, de cada lote cujo ponto interno fica fora do contorno do próprio município."""
    contornos = camadaLimites.set_index("municipio").geometry
    alvo = camadaLotes["municipio"].map(contornos).to_numpy()
    semContorno = pd.isna(alvo)
    alvo[semContorno] = None
    shapely.prepare(alvo)
    pontos = camadaLotes.representative_point().to_numpy()
    dentro = shapely.within(pontos, alvo) | semContorno
    distancias = shapely.distance(camadaLotes.geometry.to_numpy()[~dentro], alvo[~dentro])
    return pd.Series(distancias, index=camadaLotes.index[~dentro])


def gravarShapefile(camada: gpd.GeoDataFrame, caminho: Path) -> None:
    """Shapefile em UTF-8, com dt_criacao no tipo Date do DBF e campos do tamanho dos dados."""
    if "dt_criacao" in camada:
        camada = camada.assign(dt_criacao=camada["dt_criacao"].dt.date.astype(pd.ArrowDtype(pa.date32())))
    camada.to_file(caminho, engine="pyogrio", use_arrow=True, layer_options={"RESIZE": "YES"})


# ==================== Estilos e projeto do QGIS ====================

def corQgis(hexa: str) -> str:
    """'#ffb3b5' vira '255,179,181,255', o formato de cor do QGIS."""
    return ",".join(str(int(hexa[i:i + 2], 16)) for i in (1, 3, 5)) + ",255"


def faixaCategoria(categoria: str, moduloFiscal: float | None = None) -> tuple[str, str]:
    """Faixa da categoria em módulos fiscais e em hectares; sem o módulo fiscal, a de hectares fica vazia.

    Os limites seguem ``classificacao.classificarPorModuloFiscal``: 1 e 4 MF são
    pequena propriedade; 15 MF, média.
    """
    faixasMf = {
        CATEGORIAS[0]: "menos de 1 MF", CATEGORIAS[1]: "de 1 a 4 MF",
        CATEGORIAS[2]: "mais de 4 a 15 MF", CATEGORIAS[3]: "mais de 15 MF",
    }
    if categoria not in faixasMf:
        return "", ""
    if not moduloFiscal:
        return faixasMf[categoria], ""
    um, quatro, quinze = (formatarNumero(fator * moduloFiscal) for fator in (1, 4, 15))
    faixasHa = {
        CATEGORIAS[0]: f"menos de {um} ha", CATEGORIAS[1]: f"de {um} a {quatro} ha",
        CATEGORIAS[2]: f"mais de {quatro} a {quinze} ha", CATEGORIAS[3]: f"mais de {quinze} ha",
    }
    return faixasMf[categoria], faixasHa[categoria]


def rotuloCategoria(categoria: str, moduloFiscal: float | None) -> str:
    nomes = {CATEGORIAS[0]: "Menor que 1 MF", CATEGORIAS[1]: "Pequena", CATEGORIAS[2]: "Média", CATEGORIAS[3]: "Grande"}
    if categoria not in nomes:
        return categoria
    faixaMf, faixaHa = faixaCategoria(categoria, moduloFiscal)
    if categoria == CATEGORIAS[0]:
        return f"{nomes[categoria]} ({faixaHa})" if faixaHa else nomes[categoria]
    return f"{nomes[categoria]}: {faixaMf} ({faixaHa})" if faixaHa else f"{nomes[categoria]}: {faixaMf}"


def simboloPreenchimento(nome: str, cor: str, corContorno: str, larguraContorno: str, estilo: str = "solid"):
    simbolo = ET.Element("symbol", {
        "type": "fill", "name": nome, "alpha": "1", "clip_to_extent": "1", "force_rhr": "0",
    })
    camada = ET.SubElement(simbolo, "layer", {"class": "SimpleFill", "enabled": "1", "locked": "0", "pass": "0"})
    opcoes = ET.SubElement(camada, "Option", {"type": "Map"})
    propriedades = {
        "color": cor, "style": estilo, "joinstyle": "bevel",
        "outline_color": corContorno, "outline_style": "solid",
        "outline_width": larguraContorno, "outline_width_unit": "MM",
    }
    for chave, valor in propriedades.items():
        ET.SubElement(opcoes, "Option", {"name": chave, "type": "QString", "value": valor})
    return simbolo


def rendererLimites(recorte: Recorte):
    renderer = ET.Element("renderer-v2", {
        "type": "singleSymbol", "symbollevels": "0", "enableorderby": "0", "forceraster": "0",
    })
    simbolos = ET.SubElement(renderer, "symbols")
    largura = "0.7" if recorte.nivel == NIVEL_MUNICIPIO else "0.35"
    simbolos.append(simboloPreenchimento("0", "0,0,0,0", "20,20,20,255", largura, estilo="no"))
    return renderer


def rendererCategorias(recorte: Recorte, categoriasPresentes: list, moduloFiscal: float | None):
    renderer = ET.Element("renderer-v2", {
        "type": "categorizedSymbol", "attr": "categoria",
        "symbollevels": "0", "enableorderby": "0", "forceraster": "0",
    })
    categorias = ET.SubElement(renderer, "categories")
    simbolos = ET.SubElement(renderer, "symbols")
    # Na escala de região ou estado, um contorno opaco escureceria o mapa todo.
    corContorno, larguraContorno = ("90,90,90,255", "0.1") if recorte.nivel == NIVEL_MUNICIPIO else ("70,70,70,70", "0.05")
    for indice, categoria in enumerate(categoriasPresentes):
        ET.SubElement(categorias, "category", {
            "symbol": str(indice), "value": categoria,
            "label": rotuloCategoria(categoria, moduloFiscal), "render": "true",
        })
        cor = CORES_CATEGORIAS.get(categoria, CORES_CATEGORIAS[SEM_CLASSIFICACAO])
        simbolos.append(simboloPreenchimento(str(indice), corQgis(cor), corContorno, larguraContorno))
    return renderer


def rotulosMunicipios():
    """Nome do município sobre o centro de cada polígono, com contorno branco."""
    rotulos = ET.Element("labeling", {"type": "simple"})
    configuracao = ET.SubElement(rotulos, "settings", {"calloutType": "simple"})
    texto = ET.SubElement(configuracao, "text-style", {
        "fieldName": "municipio", "isExpression": "0", "fontSize": "8", "fontSizeUnit": "Point",
        "fontWeight": "50", "textColor": "20,20,20,255", "textOpacity": "1",
    })
    ET.SubElement(texto, "text-buffer", {
        "bufferDraw": "1", "bufferSize": "0.8", "bufferSizeUnits": "MM", "bufferColor": "255,255,255,255",
        "bufferOpacity": "1", "bufferNoFill": "1", "bufferJoinStyle": "128",
    })
    ET.SubElement(configuracao, "placement", {"placement": "1", "centroidInside": "1"})
    ET.SubElement(configuracao, "rendering", {"obstacle": "1"})
    return rotulos


def elementoCrs():
    crs = CRS.from_epsg(EPSG_SAIDA)
    srs = ET.Element("spatialrefsys", {"nativeFormat": "Wkt"})
    ET.SubElement(srs, "wkt").text = crs.to_wkt()
    ET.SubElement(srs, "srid").text = str(EPSG_SAIDA)
    ET.SubElement(srs, "authid").text = f"EPSG:{EPSG_SAIDA}"
    ET.SubElement(srs, "description").text = crs.name
    ET.SubElement(srs, "geographicflag").text = "true"
    return srs


def gravarXmlQgis(caminho: Path, raiz) -> None:
    ET.indent(raiz)
    cabecalho = "<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>\n"
    caminho.write_text(cabecalho + ET.tostring(raiz, encoding="unicode") + "\n", encoding="utf-8")


def gravarQml(caminho: Path, renderer, rotulos=None) -> None:
    atributos = {"version": VERSAO_QGIS, "styleCategories": "Symbology|Labeling" if rotulos is not None else "Symbology"}
    if rotulos is not None:
        atributos["labelsEnabled"] = "1"
    raiz = ET.Element("qgis", atributos)
    raiz.append(renderer)
    if rotulos is not None:
        raiz.append(rotulos)
    gravarXmlQgis(caminho, raiz)


def gravarProjeto(caminho: Path, titulo: str, camadas: list, extensao: tuple) -> None:
    """Projeto com caminhos relativos. A primeira camada da lista fica por cima."""
    raiz = ET.Element("qgis", {"projectname": titulo, "version": VERSAO_QGIS})
    ET.SubElement(raiz, "title").text = titulo
    ET.SubElement(raiz, "projectCrs").append(elementoCrs())

    arvore = ET.SubElement(raiz, "layer-tree-group")
    ET.SubElement(arvore, "customproperties")
    for camada in camadas:
        no = ET.SubElement(arvore, "layer-tree-layer", {
            "id": camada["id"], "name": camada["nome"], "source": camada["fonte"],
            "providerKey": "ogr", "checked": "Qt::Checked", "expanded": "1",
        })
        propriedades = ET.SubElement(no, "customproperties")
        if camada["contarFeicoes"]:
            opcoes = ET.SubElement(propriedades, "Option", {"type": "Map"})
            ET.SubElement(opcoes, "Option", {"name": "showFeatureCount", "type": "int", "value": "1"})

    limites = dict(zip(("xmin", "ymin", "xmax", "ymax"), (str(valor) for valor in extensao), strict=True))
    canvas = ET.SubElement(raiz, "mapcanvas", {"name": "theMapCanvas", "annotationsVisible": "1"})
    ET.SubElement(canvas, "units").text = "degrees"
    elementoExtensao = ET.SubElement(canvas, "extent")
    for nome, valor in limites.items():
        ET.SubElement(elementoExtensao, nome).text = valor
    ET.SubElement(canvas, "rotation").text = "0"
    ET.SubElement(canvas, "destinationsrs").append(elementoCrs())
    configuracaoVisao = ET.SubElement(raiz, "ProjectViewSettings", {"UseProjectScales": "0", "rotation": "0"})
    ET.SubElement(configuracaoVisao, "DefaultViewExtent", limites).append(elementoCrs())

    camadasProjeto = ET.SubElement(raiz, "projectlayers")
    for camada in camadas:
        atributos = {"type": "vector", "geometry": "Polygon", "wkbType": "MultiPolygon"}
        if camada["rotulos"] is not None:
            atributos["labelsEnabled"] = "1"
        mapa = ET.SubElement(camadasProjeto, "maplayer", atributos)
        ET.SubElement(mapa, "id").text = camada["id"]
        ET.SubElement(mapa, "datasource").text = camada["fonte"]
        ET.SubElement(mapa, "layername").text = camada["nome"]
        ET.SubElement(mapa, "srs").append(elementoCrs())
        ET.SubElement(mapa, "provider", {"encoding": "UTF-8"}).text = "ogr"
        mapa.append(camada["renderer"])
        if camada["rotulos"] is not None:
            mapa.append(camada["rotulos"])

    propriedades = ET.SubElement(raiz, "properties")
    caminhos = ET.SubElement(propriedades, "Paths")
    ET.SubElement(caminhos, "Absolute", {"type": "bool"}).text = "false"
    # Sem esta propriedade o QGIS ignora o projectCrs.
    sistema = ET.SubElement(propriedades, "SpatialRefSys")
    ET.SubElement(sistema, "ProjectionsEnabled", {"type": "int"}).text = "1"
    gravarXmlQgis(caminho, raiz)


# ==================== README ====================

def _tabela(linhas: list[list[str]], alinhamentos: str) -> str:
    """Tabela de texto com colunas alinhadas; 'e' alinha à esquerda e 'd' à direita."""
    larguras = [max(len(linha[i]) for linha in linhas) for i in range(len(alinhamentos))]
    saida = []
    for linha in linhas:
        celulas = [
            celula.ljust(largura) if alinhamento == "e" else celula.rjust(largura)
            for celula, largura, alinhamento in zip(linha, larguras, alinhamentos, strict=True)
        ]
        saida.append("  " + "  ".join(celulas).rstrip())
    return "\n".join(saida)


def montarReadme(recorte: Recorte, camadaLotes, camadaLimites, textoOrigem: str, textoGeracao: str = "") -> str:
    moduloUnico = camadaLimites["mod_fiscal"].iloc[0] if recorte.nivel == NIVEL_MUNICIPIO else None
    categoriasLinhas = [["Categoria", "Faixa em MF"] + (["Faixa em hectares"] if moduloUnico else []) + ["Lotes", "Área (ha)", "Cor"]]
    contagem = camadaLotes["categoria"].value_counts()
    areas = camadaLotes.groupby("categoria")["area_ha"].sum() if "area_ha" in camadaLotes else pd.Series(dtype=float)
    for categoria, cor in CORES_CATEGORIAS.items():
        if categoria not in CATEGORIAS and categoria not in contagem:
            continue
        faixaMf, faixaHa = faixaCategoria(categoria, moduloUnico)
        categoriasLinhas.append(
            [categoria, faixaMf] + ([faixaHa] if moduloUnico else [])
            + [formatarNumero(contagem.get(categoria, 0)), formatarNumero(areas.get(categoria, 0), 2),
               f"{cor} ({NOMES_CORES.get(cor, '')})"]
        )
    alinhamentoCategorias = "ee" + ("e" if moduloUnico else "") + "dde"

    if moduloUnico:
        textoModulo = (
            f"  Em {recorte.nome}, 1 módulo fiscal (MF) equivale a {formatarNumero(moduloUnico)} hectares.\n"
            "  Fonte: tabela de módulos fiscais do INCRA usada pelo miniserver."
        )
    else:
        linhasModulo = [["Município", "MF (ha)", "Lotes"]] + [
            [linha.municipio, formatarNumero(linha.mod_fiscal), formatarNumero(linha.n_lotes)]
            for linha in camadaLimites.itertuples()
        ]
        textoModulo = (
            "  O módulo fiscal varia por município. O campo mod_fiscal das duas camadas traz o\n"
            "  valor de cada um, e a categoria de cada lote usa o módulo do seu município.\n"
            "  Fonte: tabela de módulos fiscais do INCRA usada pelo miniserver.\n\n"
            + _tabela(linhasModulo, "edd")
        )

    distancias = lotesForaDoMunicipio(camadaLotes, camadaLimites)
    if distancias.empty:
        observacao = "  Todos os lotes têm o ponto interno dentro do contorno do seu município."
    else:
        areaFora = camadaLotes.loc[distancias.index, "area_ha"].sum() if "area_ha" in camadaLotes else 0
        observacao = (
            "  Os limites são os do IBGE, e o município de cada lote é o da base fundiária.\n"
            f"  {quantidadeDeLotes(len(distancias))} ({formatarNumero(areaFora)} ha)"
            f" {'tem' if len(distancias) == 1 else 'têm'} o ponto interno fora do contorno do seu município,\n"
            f"  a até {formatarNumero(distancias.max() / 1000, 1)} km dele."
        )
        if recorte.nivel == NIVEL_MUNICIPIO and "area_km2" in camadaLimites:
            areaMunicipio = camadaLimites["area_km2"].iloc[0] * 100
            if camadaLotes["area_ha"].sum() > areaMunicipio:
                observacao += (
                    f" Por isso a soma das áreas dos lotes ({formatarNumero(camadaLotes['area_ha'].sum())} ha)\n"
                    f"  passa da área do município ({formatarNumero(areaMunicipio)} ha)."
                )

    vazios = [
        modelo.format(quantidadeDeLotes(camadaLotes[coluna].isna().sum()))
        for coluna, modelo in (
            ("dt_criacao", "a data de criação está vazia em {}"),
            ("num_incra", "o número do INCRA está vazio em {}"),
        )
        if coluna in camadaLotes and camadaLotes[coluna].isna().any()
    ]
    if vazios:
        observacao += "\n  Na base, " + " e ".join(vazios) + "."
    invalidos = int((~camadaLotes.geometry.is_valid).sum())
    if invalidos:
        observacao += (
            f"\n  {quantidadeDeLotes(invalidos)} {'tem' if invalidos == 1 else 'têm'} geometria inválida na base"
            " (autointerseção, anel fora do\n"
            "  polígono etc.) e foram mantidos como estão. O QGIS os desenha, mas pode avisar da\n"
            "  orientação dos anéis ao abrir. Para análises, use Vetor > Geometria > Corrigir geometrias."
        )

    def camposDe(colunas: dict, camada) -> str:
        return "\n".join(f"  {campo:<11} {descricao}" for campo, descricao in colunas.items() if campo in camada)

    camadaLimitesNome = "contorno do município" if recorte.nivel == NIVEL_MUNICIPIO else "limites municipais"
    return f"""{recorte.titulo}
Lotes da malha fundiária e limites municipais
Gerado em {date.today():%d/%m/%Y}.

COMO ABRIR NO QGIS
  Abra o projeto {recorte.chave}.qgs (Projeto > Abrir). Se o pacote veio em .zip,
  descompacte antes: o QGIS não abre o projeto de dentro do .zip. O projeto mostra
  os limites municipais por cima dos lotes, que aparecem coloridos pela categoria,
  com a contagem de lotes na legenda. Ao abrir um shapefile sozinho, o QGIS aplica
  o estilo do .qml de mesmo nome. Mantenha os arquivos na mesma pasta: o projeto
  usa caminhos relativos.

ARQUIVOS
{_tabela([
    [f"{recorte.chave}.qgs", "projeto do QGIS"],
    [f"{recorte.arquivoLimites}.shp", f"{camadaLimitesNome} ({contar(len(camadaLimites), 'polígono', 'polígonos')})"],
    [f"{recorte.arquivoLotes}.shp", f"lotes da malha fundiária ({contar(len(camadaLotes), 'polígono', 'polígonos')})"],
    [f"{recorte.arquivoLimites}.qml", "estilo dos limites"],
    [f"{recorte.arquivoLotes}.qml", "estilo dos lotes por categoria"],
], "ee")}
  Cada .shp vem com .shx, .dbf, .prj e .cpg.

MÓDULO FISCAL
{textoModulo}

CATEGORIAS DOS LOTES
  As faixas de pequena e média propriedade são as do art. 4º da Lei 8.629/1993.
  As cores são as mesmas do dashboard.

{_tabela(categoriasLinhas, alinhamentoCategorias)}

SISTEMA DE REFERÊNCIA
  SIRGAS 2000 geográfico (EPSG:{EPSG_SAIDA}). Textos em UTF-8, conforme o .cpg.

ORIGEM
{textoOrigem.rstrip()}
  O nome do proprietário não é exportado.

CAMPOS DE {recorte.arquivoLotes}
{camposDe(COLUNAS_LOTES, camadaLotes)}

CAMPOS DE {recorte.arquivoLimites}
{camposDe(COLUNAS_LIMITES, camadaLimites)}

OBSERVAÇÕES
{observacao}
{textoGeracao}"""


# ==================== Pacote ====================

def gravarPacote(pasta: Path, recorte: Recorte, lotes, limites, textoOrigem: str, textoGeracao: str = "") -> list[Path]:
    """Grava o pacote na pasta, que é criada se preciso, e devolve os arquivos gravados."""
    camadaLotes, camadaLimites = prepararCamadas(recorte, lotes, limites)
    pasta.mkdir(parents=True, exist_ok=True)
    gravarShapefile(camadaLimites.to_crs(EPSG_SAIDA), pasta / f"{recorte.arquivoLimites}.shp")
    gravarShapefile(camadaLotes.to_crs(EPSG_SAIDA), pasta / f"{recorte.arquivoLotes}.shp")

    moduloUnico = camadaLimites["mod_fiscal"].iloc[0] if recorte.nivel == NIVEL_MUNICIPIO else None
    presentes = set(camadaLotes["categoria"].dropna())
    categoriasPresentes = [c for c in CORES_CATEGORIAS if c in presentes] + sorted(presentes - set(CORES_CATEGORIAS))
    # Com vários municípios, o nome de cada um aparece sobre o polígono.
    comRotulos = recorte.nivel != NIVEL_MUNICIPIO
    gravarQml(pasta / f"{recorte.arquivoLimites}.qml", rendererLimites(recorte), rotulosMunicipios() if comRotulos else None)
    gravarQml(pasta / f"{recorte.arquivoLotes}.qml", rendererCategorias(recorte, categoriasPresentes, moduloUnico))

    # A vista inicial cobre os limites e também os lotes que saem deles.
    limitesVista = pd.concat([camadaLimites.geometry, camadaLotes.geometry]).to_crs(EPSG_SAIDA).total_bounds
    xmin, ymin, xmax, ymax = (float(v) for v in limitesVista)
    margem = 0.03 * max(xmax - xmin, ymax - ymin)
    nomeLimites = f"Contorno de {recorte.nome}" if recorte.nivel == NIVEL_MUNICIPIO else "Limites municipais"
    camadas = [
        {
            "id": f"limites_{uuid.uuid4().hex}", "nome": nomeLimites, "fonte": f"./{recorte.arquivoLimites}.shp",
            "renderer": rendererLimites(recorte), "rotulos": rotulosMunicipios() if comRotulos else None,
            "contarFeicoes": False,
        },
        {
            "id": f"lotes_{uuid.uuid4().hex}", "nome": "Lotes por categoria", "fonte": f"./{recorte.arquivoLotes}.shp",
            "renderer": rendererCategorias(recorte, categoriasPresentes, moduloUnico), "rotulos": None,
            "contarFeicoes": True,
        },
    ]
    gravarProjeto(
        pasta / f"{recorte.chave}.qgs", f"{recorte.titulo} - malha fundiária", camadas,
        (xmin - margem, ymin - margem, xmax + margem, ymax + margem),
    )
    readme = montarReadme(recorte, camadaLotes, camadaLimites, textoOrigem, textoGeracao)
    (pasta / "README.txt").write_text(readme, encoding="utf-8")
    return [pasta / nome for nome in recorte.arquivos() if (pasta / nome).exists()]


def gerarZip(recorte: Recorte, lotes, limites, textoOrigem: str, textoGeracao: str = "") -> bytes:
    """O pacote compactado, com tudo dentro da pasta <chave>-shapefile."""
    with tempfile.TemporaryDirectory() as pastaTemporaria:
        arquivos = gravarPacote(Path(pastaTemporaria) / recorte.pasta, recorte, lotes, limites, textoOrigem, textoGeracao)
        conteudo = io.BytesIO()
        with zipfile.ZipFile(conteudo, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as arquivoZip:
            for arquivo in arquivos:
                arquivoZip.write(arquivo, f"{recorte.pasta}/{arquivo.name}")
        return conteudo.getvalue()
