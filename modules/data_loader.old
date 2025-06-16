# modules/data_loader.py

import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely import wkt
import unicodedata

_DATA_PREFIX    = 'dataset-malha-fundiaria-idace_preprocessado-'
_DATA_SUFFIX    = '.csv'
_MUNI_GEOJSON   = 'geojson-municipios_ceara-normalizado.geojson'

@st.cache_data
def get_latest_dataset(base_folder: str) -> str:
    files = [f for f in os.listdir(base_folder)
             if f.startswith(_DATA_PREFIX) and f.endswith(_DATA_SUFFIX)]
    if not files:
        raise FileNotFoundError(f"Nenhum dataset encontrado em {base_folder}")
    files.sort()
    return os.path.join(base_folder, files[-1])

@st.cache_data
def load_csv_data(base_folder: str) -> pd.DataFrame:
    """
    Lê o CSV mais recente, faz as conversões e classifica cada parcela
    em 'categoria', retornando um DataFrame com colunas:
    ['modulo_fiscal','area','geometry','nome_municipio',
     'regiao_administrativa','municipio_norm','categoria']
    """
    path = get_latest_dataset(base_folder)
    df   = pd.read_csv(path, low_memory=False)

    for col in ['modulo_fiscal','area','geom','nome_municipio','regiao_administrativa']:
        if col not in df.columns:
            raise KeyError(f"Coluna obrigatória '{col}' não encontrada.")

    df['modulo_fiscal'] = df['modulo_fiscal'].astype(float)
    df['area']          = df['area'].astype(float)

    df = df[df['geom'].notna()].copy()
    df['geometry'] = df['geom'].apply(wkt.loads)

    # normaliza nome do município
    df['municipio_norm'] = df['nome_municipio'].apply(
        lambda s: unicodedata.normalize('NFKD', s)
                         .encode('ASCII','ignore')
                         .decode().lower()
    )

    # classifica propriedade
    mf   = df['modulo_fiscal']
    area = df['area']
    df['categoria'] = np.where(
        area < mf, 'Pequena Propriedade < 1 MF',
        np.where(area <= 4*mf, 'Pequena Propriedade',
        np.where(area <=15*mf, 'Média Propriedade','Grande Propriedade'))
    )

    return df

@st.cache_resource
def load_municipios(base_folder: str) -> gpd.GeoDataFrame:
    """
    Lê o GeoJSON de municípios, detecta primeiro 'NM_MUN' e, se não achar,
    qualquer coluna que contenha 'nm' e 'mun', renomeia-a para 'nome_municipio'
    e adiciona muni['municipio_norm'].
    """
    path = os.path.join(base_folder, _MUNI_GEOJSON)
    muni = gpd.read_file(path)

    # tenta achar coluna exata 'NM_MUN'
    col_muni = next((c for c in muni.columns if c.lower() == 'nm_mun'), None)
    # senão, qualquer 'nm' + 'mun'
    if col_muni is None:
        col_muni = next((c for c in muni.columns
                         if 'nm' in c.lower() and 'mun' in c.lower()), None)
    if col_muni is None:
        raise KeyError(f"Nenhuma coluna de município encontrada em: {muni.columns.tolist()}")

    muni = muni.rename(columns={col_muni: 'nome_municipio'})
    muni['municipio_norm'] = muni['nome_municipio'].apply(
        lambda s: unicodedata.normalize('NFKD', s)
                         .encode('ASCII','ignore')
                         .decode().lower()
    )
    return muni.to_crs(epsg=4326)


# def validate_data(df: pd.DataFrame):
#     """
#     Recebe o df completo (com geometry e categoria) e retorna:
#       - df_all   (tudo)
#       - df_class (válidos para classificação)
#       - df_inter (GeoDataFrame para mapa interativo)
#       - df_ctx   (válidos para mapa contextual)
#       - counts   (dicionário de totais e descartados)
#     """
#     total       = len(df)
#     df_class    = df.dropna(subset=['modulo_fiscal','area'])
#     # criar GeoDataFrame para mapa interativo
#     df_inter    = df_class.dropna(subset=['geometry']).copy()
#     df_inter    = gpd.GeoDataFrame(df_inter, geometry='geometry', crs='EPSG:4326')
#     df_ctx      = df_class.dropna(subset=['municipio_norm'])

#     counts      = {
#         'total_carregados':       total,
#         'validos_classificacao': len(df_class),
#         'validos_mapa_interativo': len(df_inter),
#         'validos_mapa_contextual': len(df_ctx),
#         'descartados':            total - len(df_class)
#     }
#     return df, df_class, df_inter, df_ctx, counts
@st.cache_resource
def validate_data(df: pd.DataFrame):
    """
    Recebe DataFrame de load_csv_data e retorna:
      - df_all   : DataFrame completo
      - df_class : DataFrame filtrado para classificação
      - gdf_inter: GeoDataFrame pronto para mapa interativo
      - df_ctx   : DataFrame para mapa contextual
      - counts   : dict de totais e descartados
    """
    total = len(df)

    # 1) Filtra entradas com area e modulo_fiscal
    df_class = df.dropna(subset=['modulo_fiscal', 'area']).copy()

    # 2) Prepara GeoDataFrame para o mapa interativo
    df_inter = df_class.copy()
    # Converte WKT → shapely geometry
    df_inter['geometry'] = df_inter['geom'].apply(lambda w: wkt.loads(w) if pd.notna(w) else None)
    df_inter = df_inter.dropna(subset=['geometry'])
    # Monta GeoDataFrame e projeta para WGS84
    gdf_inter = gpd.GeoDataFrame(df_inter, geometry='geometry', crs='EPSG:31984')
    gdf_inter = gdf_inter.to_crs(epsg=4326)

    # 3) Classifica categorias direto no GeoDataFrame
    conds = [
        (gdf_inter['area'] > 0) & (gdf_inter['area'] < gdf_inter['modulo_fiscal']),
        (gdf_inter['area'] >= gdf_inter['modulo_fiscal']) & (gdf_inter['area'] <= 4 * gdf_inter['modulo_fiscal']),
        (gdf_inter['area'] > 4 * gdf_inter['modulo_fiscal']) & (gdf_inter['area'] <= 15 * gdf_inter['modulo_fiscal']),
        (gdf_inter['area'] > 15 * gdf_inter['modulo_fiscal'])
    ]
    cats = ['Pequena Propriedade < 1 MF', 'Pequena Propriedade', 'M\u00e9dia Propriedade', 'Grande Propriedade']
    gdf_inter['categoria'] = np.select(conds, cats, default='Sem Classificação')

    # 4) Prepara dados para o mapa contextual
    df_ctx = df_class.dropna(subset=['municipio_norm']).copy()

    # 5) Contagens de validação
    counts = {
        'total_carregados': total,
        'validos_classificacao': len(df_class),
        'validos_mapa_interativo': len(gdf_inter),
        'validos_mapa_contextual': len(df_ctx),
        'descartados': total - len(df_class)
    }

    return df, df_class, gdf_inter, df_ctx, counts
