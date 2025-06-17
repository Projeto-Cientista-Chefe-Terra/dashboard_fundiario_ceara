# modules/data_loader.py

import os
import requests
import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import shape
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor

# Configuração ajustável da API
DATA_SERVICE_URL = st.secrets.get("DATA_SERVICE_URL", "http://localhost:8000")
REQUEST_TIMEOUT = 30  # segundos
MAX_WORKERS = 4  # Para requests paralelos

@st.cache_data(ttl=86400)  # Cache de 24h para dados estáticos
def _fetch_from_api(endpoint: str, params: Optional[Dict] = None) -> Any:
    """Helper function otimizado para fetch de dados"""
    try:
        response = requests.get(
            f"{DATA_SERVICE_URL}/{endpoint}",
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao acessar API: {str(e)}")
        raise

@st.cache_data(ttl=3600)  # Cache de 1h para dados regionais
def _fetch_regiao_data(regiao: str) -> List[Dict]:
    """Busca dados de uma região específica com tratamento de erro"""
    try:
        return _fetch_from_api("dados_fundiarios", {"regiao": regiao})
    except:
        return []

@st.cache_data(ttl=3600)
def load_csv_data(base_folder: str) -> pd.DataFrame:
    """Carrega dados de forma otimizada com paralelismo"""
    # Busca regiões (cache longo)
    regions = _fetch_from_api("regioes")["regioes"]
    
    # Busca paralela por região
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        all_data = []
        for data in executor.map(_fetch_regiao_data, regions):
            all_data.extend(data)
    
    # Cria DataFrame otimizado
    df = pd.DataFrame(all_data, columns=[
        'imovel','data_criacao_lote', 'numero_incra',
        'numero_lote', 'area','situacao_juridica','regiao_administrativa',
        'nome_municipio_original', 'distrito', 
        'localidade', 'categoria', 'geometry', 'nome_municipio','modulo_fiscal','lote_id'
    ])
    
    # Tipos específicos para economizar memória
    df['modulo_fiscal'] = pd.to_numeric(df['modulo_fiscal'], errors='coerce')
    df['area'] = pd.to_numeric(df['area'], errors='coerce')
    df['municipio_norm'] = df['nome_municipio'].str.lower().astype('category')
    
    return df

@st.cache_resource(ttl=86400)
def load_municipios(base_folder: str) -> gpd.GeoDataFrame:
    """Carrega municípios com geometrias simplificadas"""
    # Busca lista de municípios (cache longo)
    muni_list = _fetch_from_api("municipios_todos")["municipios"]
    
    # Busca geometrias com parâmetro de simplificação
    features = []
    for muni in muni_list[:50]:  # Limite para teste - ajustar conforme necessário
        try:
            geojson = _fetch_from_api(
                "geojson_muni", 
                {"municipio": muni, "tolerance": 0.01}
            )
            features.extend(geojson["features"])
        except:
            continue
    
    # Cria GeoDataFrame otimizado
    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    
    # Normaliza colunas
    if 'nm_mun' in gdf.columns:
        gdf = gdf.rename(columns={'nm_mun': 'nome_municipio'})
    gdf['municipio_norm'] = gdf['nome_municipio'].str.lower().astype('category')
    
    return gdf[['nome_municipio', 'municipio_norm', 'geometry']]

@st.cache_resource
def validate_data(df: pd.DataFrame) -> tuple:
    """Versão otimizada da validação de dados"""
    # Filtra dados inválidos
    df_class = df.dropna(subset=['modulo_fiscal', 'area']).copy()
    
    # Pré-classificação sem geometria
    conditions = [
        (df_class['area'] < df_class['modulo_fiscal']),
        (df_class['area'] <= 4 * df_class['modulo_fiscal']),
        (df_class['area'] <= 15 * df_class['modulo_fiscal']),
        (df_class['area'] > 15 * df_class['modulo_fiscal'])
    ]
    choices = [
        'Pequena Propriedade < 1 MF',
        'Pequena Propriedade', 
        'Média Propriedade',
        'Grande Propriedade'
    ]
    df_class['categoria'] = np.select(conditions, choices, default='Sem Classificação')
    
    # Contagens básicas
    counts = {
        'total_carregados': len(df),
        'validos_classificacao': len(df_class),
        'validos_mapa_contextual': df_class['nome_municipio'].notna().sum(),
        'descartados': len(df) - len(df_class)
    }
    
    # Retorna sem geometrias para mapas interativos (serão carregados sob demanda)
    return df, df_class, None, df_class.dropna(subset=['nome_municipio']), counts