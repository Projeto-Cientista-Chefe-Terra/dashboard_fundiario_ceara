# modules/data_loader.py


import os
import json
import requests
import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
from typing import Dict, List, Any, Optional

# Configuração ajustável da API
DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://localhost:8000")
REQUEST_TIMEOUT = 120  # segundos

@st.cache_data(ttl=86400)
def _fetch_from_api(endpoint: str, params: Optional[Dict] = None) -> Any:
    """Helper function com tratamento robusto de erros"""
    try:
        st.session_state.setdefault('api_calls', 0)
        st.session_state.api_calls += 1
        
        response = requests.get(
            f"{DATA_SERVICE_URL}/{endpoint}",
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        
        # Verificação especial para evitar erro com endpoint /version
        if endpoint == "version":
            if response.status_code == 404:
                return {'data_version': '1.0.0-default'}  # Versão padrão
            response.raise_for_status()
            return response.json()
        else:
            response.raise_for_status()
            return response.json()
            
    except requests.exceptions.RequestException as e:
        if endpoint == "version":
            return {'data_version': '1.0.0-fallback'}  # Versão de fallback
        
        # Fallback para dados locais se disponível
        if os.path.exists(f"backup/{endpoint}.json"):
            with open(f"backup/{endpoint}.json") as f:
                return json.load(f)
        st.error(f"Erro ao acessar endpoint {endpoint}: {str(e)}")
        raise

@st.cache_data(ttl=3600)
def _fetch_regiao_data(regiao: str) -> List[Dict]:
    """Busca dados de uma região específica"""
    try:
        data = _fetch_from_api("dados_fundiarios", {"regiao": regiao})
        return data if isinstance(data, list) else []
    except Exception:
        return []

@st.cache_data(ttl=3600)
def _fetch_all_regions_data(regions: List[str]) -> List[Dict]:
    """Busca dados de todas as regiões"""
    all_data = []
    for region in regions:
        try:
            region_data = _fetch_regiao_data(region)
            if region_data:
                all_data.extend(region_data)
        except Exception:
            continue
    return all_data

@st.cache_data(ttl=3600)
def load_csv_data(base_folder: str) -> pd.DataFrame:
    """Carrega dados principais"""
    try:
        # Busca dados básicos sem depender do endpoint /version
        regions = _fetch_from_api("regioes").get("regioes", [])
        all_data = _fetch_all_regions_data(regions)
        
        if not all_data:
            st.error("Nenhum dado foi carregado - verifique a conexão com a API")
            return pd.DataFrame()

        # Cria DataFrame otimizado
        df = pd.DataFrame(all_data, columns=[
            'imovel','data_criacao_lote', 'numero_incra',
            'numero_lote', 'area','situacao_juridica','regiao_administrativa',
            'nome_municipio_original', 'distrito', 'localidade', 
            'categoria', 'geometry', 'nome_municipio','modulo_fiscal','lote_id'
        ])
        
        # Conversão de tipos segura
        numeric_cols = ['modulo_fiscal', 'area']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        return df.convert_dtypes()
        
    except Exception as e:
        st.error(f"Falha crítica ao carregar dados: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def _fetch_municipality_geojson(municipio: str) -> Dict:
    """Busca GeoJSON individual com fallback"""
    try:
        return _fetch_from_api(
            "geojson_muni", 
            {"municipio": municipio, "tolerance": 0.01}
        ) or {}
    except Exception:
        return {}

@st.cache_resource(ttl=86400)
def load_municipios(base_folder: str) -> gpd.GeoDataFrame:
    """Carrega municípios com fallback robusto"""
    try:
        muni_list = _fetch_from_api("municipios_todos").get("municipios", [])
        features = []
        
        for muni in muni_list:
            geojson = _fetch_municipality_geojson(muni)
            if geojson and 'features' in geojson:
                features.extend(geojson['features'])
        
        if not features:
            st.warning("Nenhuma geometria de município carregada")
            return gpd.GeoDataFrame()
            
        return gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
        
    except Exception as e:
        st.error(f"Falha ao carregar municípios: {str(e)}")
        return gpd.GeoDataFrame()

@st.cache_resource
def validate_data(df: pd.DataFrame) -> tuple:
    """Validação com tratamento de erros"""
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), None, pd.DataFrame(), {}
    
    try:
        df_class = df.dropna(subset=['modulo_fiscal', 'area']).copy()
        
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
        
        counts = {
            'total_carregados': len(df),
            'validos_classificacao': len(df_class),
            'validos_mapa_contextual': df_class['nome_municipio'].notna().sum(),
            'descartados': len(df) - len(df_class),
            'versao_dados': _fetch_from_api("version").get('data_version', 'desconhecida')
        }
        
        return (
            df,
            df_class,
            None,  # Geometrias serão carregadas sob demanda
            df_class.dropna(subset=['nome_municipio']),
            counts
        )
        
    except Exception as e:
        st.error(f"Erro na validação dos dados: {str(e)}")
        return df, df, None, df, {}


@st.cache_data(ttl=7200)
def fetch_regioes() -> list[str]:
    resp = requests.get(f"{DATA_SERVICE_URL}/regioes", timeout=20)
    resp.raise_for_status()
    return resp.json().get("regioes", [])

@st.cache_data(ttl=7200)
def fetch_municipios(regiao: str) -> list[str]:
    resp = requests.get(f"{DATA_SERVICE_URL}/municipios", params={"regiao": regiao}, timeout=20)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json().get("municipios", [])

@st.cache_data(ttl=1200)
def fetch_geojson_por_regiao(regiao: str) -> dict:
    resp = requests.get(f"{DATA_SERVICE_URL}/geojson", params={"regiao": regiao}, timeout=20)
    resp.raise_for_status()
    return resp.json()

@st.cache_data(ttl=1200)
def fetch_geojson_por_municipio(municipio: str) -> dict:
    resp = requests.get(f"{DATA_SERVICE_URL}/geojson", params={"municipio": municipio}, timeout=20)
    resp.raise_for_status()
    return resp.json()

@st.cache_data(ttl=7200)
def fetch_geojson_limites(municipio: str) -> dict:
    """
    Chama GET /geojson_muni?municipio=YYY e retorna o FeatureCollection do município (limite administrativo).
    """
    resp = requests.get(f"{DATA_SERVICE_URL}/geojson_muni", params={"municipio": municipio}, timeout=20)
    resp.raise_for_status()
    return resp.json()
