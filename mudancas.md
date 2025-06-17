
### Resumão dos seus Endpoints Principais:

* `/regioes` → Lista todas as regiões
* `/municipios?regiao=...` → Lista municípios de uma região
* `/municipios_todos` → Lista todos municípios
* `/dados_fundiarios?regiao=...` ou `?municipio=...` → Dados tabulares, sem geometria
* `/geojson_muni?municipio=...` → GeoJSON com geometria do município (da tabela de municípios)
* `/geojson?regiao=...` ou `?municipio=...` → GeoJSON de lotes fundiários por região ou município, **com propriedades** das terras/lotes
* `/health` → healthcheck


---

## 🔥 **PASSO A PASSO PRÁTICO (Agora super alinhado com sua API):**

---

### **1️⃣ Melhore seu `data_loader.py` para refletir seus endpoints**

#### a) **Funções para listagem básica**

```python
@st.cache_data(ttl=3600)
def fetch_regioes() -> list:
    return _fetch_from_api("regioes")["regioes"]

@st.cache_data(ttl=3600)
def fetch_municipios(regiao: str) -> list:
    return _fetch_from_api("municipios", {"regiao": regiao})["municipios"]

@st.cache_data(ttl=3600)
def fetch_todos_municipios() -> list:
    return _fetch_from_api("municipios_todos")["municipios"]
```

#### b) **Dados fundiários (tabulares, SEM geometria)**

```python
@st.cache_data(ttl=3600)
def fetch_dados_fundiarios_por_regiao(regiao: str) -> list:
    return _fetch_from_api("dados_fundiarios", {"regiao": regiao})

@st.cache_data(ttl=3600)
def fetch_dados_fundiarios_por_municipio(municipio: str) -> list:
    return _fetch_from_api("dados_fundiarios", {"municipio": municipio})
```

#### c) **Dados geoespaciais (GeoJSON)**

* **Município (apenas geometria do município):**

```python
@st.cache_data(ttl=3600)
def fetch_geojson_muni(municipio: str) -> dict:
    return _fetch_from_api("geojson_muni", {"municipio": municipio})
```

* **Região ou município (lotes fundiários + propriedades + geometria):**

```python
@st.cache_data(ttl=3600)
def fetch_geojson_lotes_por_regiao(regiao: str, tolerance=0.01, decimals=6) -> dict:
    return _fetch_from_api("geojson", {"regiao": regiao, "tolerance": tolerance, "decimals": decimals})

@st.cache_data(ttl=3600)
def fetch_geojson_lotes_por_municipio(municipio: str, tolerance=0.01, decimals=6) -> dict:
    return _fetch_from_api("geojson", {"municipio": municipio, "tolerance": tolerance, "decimals": decimals})
```

---

### **2️⃣ Atualize o carregamento e merge dos dados**

#### a) **Carregar todos os dados tabulares fundiários via API**

```python
@st.cache_data(ttl=3600)
def load_todos_dados_fundiarios() -> pd.DataFrame:
    regioes = fetch_regioes()
    # Carrega dados de cada região e concatena
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        dfs = list(executor.map(fetch_dados_fundiarios_por_regiao, regioes))
    # dfs é uma lista de listas de dicts
    df = pd.DataFrame([item for sublist in dfs for item in sublist])
    # Normaliza nomes (veja dica da função normalizar_nome no passo anterior)
    df['municipio_norm'] = df['nome_municipio'].apply(normalizar_nome).astype('category')
    return df
```

#### b) **Carregar todas as geometrias dos municípios**

```python
@st.cache_data(ttl=86400)
def load_todas_geometrias_municipios() -> gpd.GeoDataFrame:
    municipios = fetch_todos_municipios()
    features = []
    for muni in municipios:
        try:
            geojson = fetch_geojson_muni(muni)
            features.extend(geojson["features"])
        except Exception:
            continue
    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    gdf['municipio_norm'] = gdf['nome_municipio'].apply(normalizar_nome).astype('category')
    return gdf[['nome_municipio', 'municipio_norm', 'geometry']]
```

---

### **3️⃣ (Opcional) Adicione funções de utilidade para merge/mapa contextual**

```python
def preparar_dados_ctx(df_ctx: pd.DataFrame, gdf_muni: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf_muni.merge(df_ctx, on='municipio_norm', how='left')
```

---

### **4️⃣ Adapte o `app.py` para usar exclusivamente essas funções**

#### a) **No início do app.py:**

```python
from modules.data_loader import (
    load_todos_dados_fundiarios, load_todas_geometrias_municipios,
    fetch_geojson_lotes_por_regiao, fetch_geojson_lotes_por_municipio,
    fetch_regioes, fetch_municipios, preparar_dados_ctx, # etc.
)
```

#### b) **Carregamento centralizado:**

```python
df_all = load_todos_dados_fundiarios()
# Depois, se precisar classificar:
df_all, df_class, _, df_ctx, counts = validate_data(df_all)
gdf_muni = load_todas_geometrias_municipios()
```

#### c) **Nos mapas interativos, sempre use as funções de fetch\_geojson do novo data\_loader**

---

## 🦾 **Fluxo para ir mudando e testando** (incremental):

1. **Adicione todas as funções acima no seu data\_loader.py**
2. **No app.py, remova todos os imports/uso do antigo data\_loader\_aux.py**
3. **Faça a aba de gráficos/tabelas só usar df\_all/df\_class do novo loader**
4. **Adapte Mapa Contextual para usar preparar\_dados\_ctx(df\_ctx, gdf\_muni)**
5. **Adapte Mapa Interativo para usar fetch\_geojson\_lotes\_por\_regiao ou fetch\_geojson\_lotes\_por\_municipio**
6. **(Opcional) Adapte Mapa Gini para usar os dados fundiários do loader (nunca do CSV!)**

Teste cada aba **depois de cada mudança**.

---

## 🚦 **DICA NINJA:**

No início de cada aba, coloque temporariamente um:

```python
st.write(df_all.head())
st.write(gdf_muni.head())
```