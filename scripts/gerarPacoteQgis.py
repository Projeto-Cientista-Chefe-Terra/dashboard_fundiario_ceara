"""Gera o pacote do QGIS (lotes e limites municipais) a partir dos CSVs do miniserver.

Uso, com o Python do dashboard:
    python scripts/gerarPacoteQgis.py municipio salitre
    python scripts/gerarPacoteQgis.py regiao cariri
    python scripts/gerarPacoteQgis.py estado
    python scripts/gerarPacoteQgis.py --listar

O nome vai sem acento, em minúsculas e com "_" no lugar dos espaços, como nas
tabelas do miniserver (juazeiro_do_norte, litoral_oeste_vale_do_curu). O pacote
fica em <destino>/<nome>-shapefile. É o mesmo pacote que o dashboard gera na
página Exportar para o QGIS, mas com a geometria original dos limites municipais
e o lote_id, que a API não entrega. A montagem fica em modules/exportacaoQgis.py.
"""
import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from modules import exportacaoQgis  # noqa: E402

PASTA_DATASETS_PADRAO = RAIZ.parent / "terraGeoDataMiniServer" / "datasets"
CSV_MALHA = "malha_fundiaria_ceara.csv"
CSV_MUNICIPIOS = "municipios_ceara.csv"
COLUNAS_MALHA = {
    "lote_id": "lote_id", "imovel": "nome_lote", "data_criacao_lote": "dt_criacao", "numero_incra": "num_incra",
    "numero_lote": "num_lote", "area": "area_ha", "situacao_juridica": "sit_jurid", "categoria": "categoria",
}

TEXTO_ORIGEM = f"""  Os CSVs que o terraGeoDataMiniServer carrega no Postgres a cada inicialização
  ({CSV_MALHA} e {CSV_MUNICIPIOS}). A geometria dos lotes e
  dos limites é a original, sem a simplificação aplicada pela API."""


def textoGeracao(pastaDatasets: Path) -> str:
    return f"""
GERAR OUTRO PACOTE
  Pelo dashboard: página Exportar para o QGIS. Pela linha de comando, com o Python
  do dashboard, a partir da pasta dashboard_fundiario_ceara:

    .venv/bin/python scripts/gerarPacoteQgis.py municipio juazeiro_do_norte
    .venv/bin/python scripts/gerarPacoteQgis.py regiao litoral_oeste_vale_do_curu
    .venv/bin/python scripts/gerarPacoteQgis.py estado

  O nome vai sem acento, em minúsculas e com "_" no lugar dos espaços. Opções:
    --destino PASTA    onde criar a pasta do pacote (padrão: diretório atual)
    --datasets PASTA   pasta dos CSVs (padrão: {pastaDatasets})
    --sobrescrever     refaz os arquivos de um pacote já gerado
    --listar           mostra as regiões, os municípios e quantos lotes cada um tem
"""


def lerCsv(caminho: Path, colunas=None) -> pd.DataFrame:
    if not caminho.exists():
        sys.exit(f"Arquivo não encontrado: {caminho}. Indique a pasta dos CSVs com --datasets.")
    return pd.read_csv(caminho, dtype=str, keep_default_na=False, usecols=colunas)


def lerEwkb(serie: pd.Series) -> tuple:
    """Geometrias de uma coluna EWKB em hexadecimal e o SRID gravado nelas."""
    geometrias = shapely.from_wkb(serie.replace("", None).to_numpy())
    srids = {shapely.get_srid(g) for g in geometrias if g is not None}
    if len(srids) != 1:
        raise ValueError(f"Esperava um único SRID nas geometrias, encontrei {srids}.")
    return geometrias, srids.pop()


def chavesDaMalha(malha: pd.DataFrame) -> pd.Series:
    chaves = {nome: exportacaoQgis.normalizarNome(nome) for nome in malha["nome_municipio"].unique()}
    return malha["nome_municipio"].map(chaves)


def lerLotes(pastaDatasets: Path, chaves: list[str]) -> gpd.GeoDataFrame:
    malha = lerCsv(pastaDatasets / CSV_MALHA, ["nome_municipio", "geometry_31984", *COLUNAS_MALHA])
    malha["chave"] = chavesDaMalha(malha)
    malha = malha[malha["chave"].isin(chaves)]
    if malha.empty:
        return gpd.GeoDataFrame({"chave": []}, geometry=[], crs=exportacaoQgis.EPSG_METRICO)
    geometrias, srid = lerEwkb(malha["geometry_31984"])
    dados = malha[["chave", *COLUNAS_MALHA]].rename(columns=COLUNAS_MALHA)
    dados["lote_id"] = dados["lote_id"].astype("int64")
    return gpd.GeoDataFrame(dados, geometry=geometrias, crs=srid)


def lerLimites(pastaDatasets: Path) -> gpd.GeoDataFrame:
    municipios = lerCsv(pastaDatasets / CSV_MUNICIPIOS, ["nm_mun", "area_km2", "geometry"])
    geometrias, srid = lerEwkb(municipios["geometry"])
    return gpd.GeoDataFrame(
        {"chave": municipios["nm_mun"].map(exportacaoQgis.normalizarNome), "area_km2": municipios["area_km2"]},
        geometry=geometrias,
        crs=srid,
    )


def montarRecorte(nivel: str, nome: str | None) -> exportacaoQgis.Recorte:
    if nivel == exportacaoQgis.NIVEL_ESTADO:
        return exportacaoQgis.recorteEstado()
    if not nome:
        sys.exit(f"Informe o nome: gerarPacoteQgis.py {nivel} <nome>. Use --listar para ver os nomes.")
    return exportacaoQgis.recorteMunicipio(nome) if nivel == exportacaoQgis.NIVEL_MUNICIPIO else exportacaoQgis.recorteRegiao(nome)


def gerar(recorte: exportacaoQgis.Recorte, pastaDatasets: Path, destino: Path, sobrescrever: bool) -> Path:
    pasta = destino / recorte.pasta
    existentes = [pasta / nome for nome in recorte.arquivos() if (pasta / nome).exists()]
    if existentes and not sobrescrever:
        sys.exit(f"A pasta {pasta} já tem um pacote gerado. Use --sobrescrever para refazê-lo.")
    lotes = lerLotes(pastaDatasets, recorte.chavesMunicipios())
    limites = lerLimites(pastaDatasets)
    for arquivo in existentes:
        arquivo.unlink()
    exportacaoQgis.gravarPacote(pasta, recorte, lotes, limites, TEXTO_ORIGEM, textoGeracao(pastaDatasets))
    return pasta


def listar(pastaDatasets: Path) -> None:
    malha = lerCsv(pastaDatasets / CSV_MALHA, ["nome_municipio"])
    lotesPorChave = chavesDaMalha(malha).value_counts()
    porRegiao = {}
    for chave, municipio in sorted(exportacaoQgis.MUNICIPIOS_POR_CHAVE.items()):
        porRegiao.setdefault(municipio.regiao, []).append((chave, municipio))
    print("estado (ceara)", exportacaoQgis.formatarNumero(lotesPorChave.sum()), "lotes\n")
    for regiao, municipios in sorted(porRegiao.items()):
        totalRegiao = sum(lotesPorChave.get(chave, 0) for chave, _ in municipios)
        print(f"regiao {exportacaoQgis.normalizarNome(regiao)}  ({regiao}, {exportacaoQgis.formatarNumero(totalRegiao)} lotes)")
        for chave, municipio in municipios:
            print(f"  municipio {chave:<28} MF {exportacaoQgis.formatarNumero(municipio.moduloFiscal):>3} ha"
                  f"  {exportacaoQgis.formatarNumero(lotesPorChave.get(chave, 0)):>7} lotes")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("nivel", nargs="?", choices=[exportacaoQgis.NIVEL_MUNICIPIO, exportacaoQgis.NIVEL_REGIAO, exportacaoQgis.NIVEL_ESTADO])
    parser.add_argument("nome", nargs="?", help='nome sem acento, minúsculo, com "_" (ex.: juazeiro_do_norte)')
    parser.add_argument("--destino", type=Path, default=Path.cwd(), help="onde criar a pasta do pacote")
    parser.add_argument("--datasets", type=Path, default=PASTA_DATASETS_PADRAO, help="pasta dos CSVs do miniserver")
    parser.add_argument("--sobrescrever", action="store_true", help="refaz os arquivos de um pacote já gerado")
    parser.add_argument("--listar", action="store_true", help="lista as regiões e os municípios")
    argumentos = parser.parse_args()

    pastaDatasets = argumentos.datasets.expanduser()
    if argumentos.listar:
        listar(pastaDatasets)
        return
    if not argumentos.nivel:
        parser.error("informe municipio <nome>, regiao <nome> ou estado; ou use --listar")
    try:
        recorte = montarRecorte(argumentos.nivel, argumentos.nome)
        pasta = gerar(recorte, pastaDatasets, argumentos.destino.expanduser(), argumentos.sobrescrever)
    except exportacaoQgis.ErroRecorte as erro:
        sys.exit(str(erro))
    print(f"Pronto: {pasta}")


if __name__ == "__main__":
    main()
