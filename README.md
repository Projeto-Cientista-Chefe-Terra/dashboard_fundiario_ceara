# dashboard_fundiario_ceara
Aplicação Web de Análise e Visualização dos dados de concentração fundiária do Ceará

## Requisitos Funcionais
| ID   | User Story                                                                                                                 |
| ---- | -------------------------------------------------------------------------------------------------------------------------- |
| RF01 | Como usuário, quero visualizar o mapa interativo das propriedades rurais do Ceará para analisar a concentração fundiária.  |
| RF02 | Como usuário, quero visualizar gráficos interativos (barra, pizza, cumulativo) das classificações das propriedades rurais. |
| RF03 | Como usuário, quero poder selecionar municípios específicos para filtrar a visualização dos mapas e gráficos.              |
| RF04 | Como usuário, quero acessar informações detalhadas sobre cada propriedade ao clicar no mapa.                               |

## Requisitos Não Funcionais
| ID    | Requisito Não Funcional                                                           |
| ----- | --------------------------------------------------------------------------------- |
| RNF01 | O sistema deve ser responsivo, funcionando bem em desktops e dispositivos móveis. |
| RNF02 | A aplicação deve carregar rapidamente gráficos e mapas (alta performance).        |
| RNF03 | O código deve ser modular, claro e bem documentado.                               |

## Camada base dos mapas (CARTO)

Os mapas usam os basemaps raster da CARTO, que desde 2025 exigem uma API key.
Sem a chave os tiles continuam sendo servidos, porém cobertos pela marca d'água
*API key required*.

A chave é lida por `modules/basemap.py`, nesta ordem de precedência:

1. variável de ambiente `CARTO_API_KEY`;
2. `st.secrets["CARTO_API_KEY"]`, vinda de `.streamlit/secrets.toml`.

Se nenhuma das duas estiver preenchida, o dashboard usa o OpenStreetMap como
camada base. Isso é proposital: um mapa com outra aparência é preferível a um
mapa com marca d'água.

### Restrição por domínio

A chave do projeto está restrita ao domínio `terrace.virtual.ufc.br` no painel
da CARTO. A validação é feita pelo cabeçalho `Referer` enviado pelo navegador,
então requisições de qualquer outra origem recebem HTTP 403 e os tiles ficam
cinza. Consequências práticas:

- em produção, basta a variável `CARTO_API_KEY` estar definida no container;
- em desenvolvimento local, `CARTO_API_KEY` deve ficar **vazia**, para que o
  OpenStreetMap seja usado. Para usar os tiles da CARTO localmente, libere
  `localhost` nas restrições da chave em <https://carto.com/basemaps/apikey>.

Como a checagem depende do navegador, o servidor não consegue validar a chave
sozinho: um teste feito a partir do backend é rejeitado mesmo com a chave certa.

### Configuração

| Ambiente          | Onde definir                                          |
| ----------------- | ----------------------------------------------------- |
| Desenvolvimento   | `export CARTO_API_KEY=...` no shell, ou `.streamlit/secrets.toml` |
| docker-compose    | `.env`, repassado ao serviço `dfundce`                |
| Portainer         | variável de ambiente `CARTO_API_KEY` do container     |

No Portainer, cole o valor da chave **sem aspas**.

A atribuição da CARTO e do OpenStreetMap é obrigatória e já acompanha a camada
base em todos os mapas (<https://carto.com/attributions>).

Não declare no `secrets.toml` uma chave que também venha do ambiente. O
`streamlit run` copia o arquivo para `os.environ` ao iniciar e o valor do
arquivo passa por cima da variável do container.

## Estrutura do código

`app.py` só configura a página, aplica o CSS, monta o menu e chama a página
ativa. O resto fica em `modules/`:

| Módulo | Papel |
| ------ | ----- |
| `config.py` | URL do miniserver, timeouts, TTL do cache e `JWT_SECRET` |
| `apiCliente.py` | Cliente HTTP único: sessão reaproveitada, token JWT e `ErroApi` |
| `repositorio.py` | Uma função com cache por endpoint do miniserver |
| `classificacao.py` | Faixas de módulo fiscal (única implementação) |
| `privacidade.py` | Nome de proprietário conforme a LGPD e escape de HTML |
| `camadasMapa.py`, `basemap.py` | Camadas, controles e camada base dos mapas |
| `componentesUi.py` | Trechos de interface repetidos entre páginas |
| `navegacao.py` | Tabela de páginas e menu lateral |
| `exportacaoQgis.py` | Pacote para o QGIS: shapefiles, estilos, projeto e README |
| `pagina*.py` | Uma página do dashboard por módulo |

Os dados são recarregados do miniserver a cada 24 horas (`config.TTL_DADOS`).
O miniserver recebe a carga nova uma vez por mês.

## Exportação para o QGIS

A página **Exportar para o QGIS** gera um `.zip` com os lotes de um município,
de uma região administrativa ou do estado, para abrir no QGIS:

- `<nome>_lotes.shp`: os lotes, coloridos pela categoria de tamanho em módulos
  fiscais, com as mesmas cores do dashboard;
- `<nome>_municipio.shp` ou `<nome>_municipios.shp`: os limites municipais, com
  o nome de cada município na região e no estado;
- um `.qml` por camada, um projeto `<nome>.qgs` que abre as duas já estilizadas
  e um `README.txt` com o módulo fiscal, as faixas das categorias e os campos.

O nome do proprietário nunca é exportado. A montagem fica em
`modules/exportacaoQgis.py`, que não depende do Streamlit. Na página, os lotes vêm
da API sem simplificação (`tolerance=0`) e cada pacote fica em cache pela versão
dos dados. Os limites municipais vêm simplificados pela API (cerca de 100 m).

O mesmo pacote pode ser gerado pela linha de comando, a partir dos CSVs do
miniserver, com a geometria original dos limites e o `lote_id`:

```bash
python scripts/gerarPacoteQgis.py municipio salitre
python scripts/gerarPacoteQgis.py regiao litoral_oeste_vale_do_curu
python scripts/gerarPacoteQgis.py estado --destino ~/temp
python scripts/gerarPacoteQgis.py --listar
```

O nome vai sem acento, em minúsculas e com `_` no lugar dos espaços. Os CSVs são
lidos de `../terraGeoDataMiniServer/datasets` (outra pasta com `--datasets`).

## Configuração

| Variável | Uso |
| -------- | --- |
| `DATA_SERVICE_URL` | Endereço do miniserver, sem `/api`. Padrão: `http://localhost:8000` |
| `JWT_SECRET` | Segredo compartilhado com o miniserver. Em produção vem do ambiente; no desenvolvimento pode ficar no `.streamlit/secrets.toml` |
| `CARTO_API_KEY` | Chave dos basemaps da CARTO (ver seção acima) |

A imagem Docker não inclui o `.streamlit/secrets.toml`. A troca anual dos
segredos está descrita em [`doc/rotacao_segredos.md`](doc/rotacao_segredos.md).

## Desenvolvimento

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
streamlit run app.py
```

```bash
ruff check .                  # lint
python -m pytest -q           # testes, sem precisar do miniserver
python -m tests.benchPaginas  # benchmark das páginas com dados sintéticos
```

As versões ficam fixadas em `requirements.txt` e `requirements-dev.txt`. Para
atualizar, ajuste o ambiente a partir de `requirements.in` e
`requirements-dev.in`, rode os testes e depois `python scripts/fixarDependencias.py`.

## Convenção de nomes

O projeto usa camelCase, com identificadores em português e sem acentos:

- funções, variáveis e parâmetros em lowerCamelCase: `carregarLotes`;
- classes em UpperCamelCase: `ErroApi`;
- constantes em MAIUSCULAS_COM_SUBLINHADO: `CENTRO_CEARA`;
- módulos em lowerCamelCase: `camadasMapa.py`.

Ficam de fora os nomes de bibliotecas externas, as colunas e chaves JSON que vêm
do miniserver (como `nome_municipio`) e o prefixo `test_` do pytest. O teste
`tests/test_convencaoNomes.py` verifica a convenção.

## Dados pessoais (LGPD)

O nome de proprietário pessoa física não é exibido: no mapa da malha fundiária
ele aparece como "Pessoa física (protegido pela LGPD)". O nome é exibido só
quando identifica com segurança uma pessoa jurídica ou um ente público, como
`LTDA`, `S/A`, associação, cooperativa ou prefeitura. Espólio e empresário
individual (ME, MEI, EIRELI) ficam ocultos. A regra está em
`modules/privacidade.py`, e o mascaramento acontece no servidor, antes de o mapa
chegar ao navegador.

Desde a versão 1.2.0, o miniserver já entrega o nome protegido pela mesma regra
e um pseudônimo (`id_proprietario`) para o cálculo do Índice de Gini. O dashboard
mantém o mascaramento como segunda barreira.

## Versão dos dados

O dashboard consulta `/versao_dados` no miniserver a cada 5 minutos. Quando uma
carga nova termina, o cache é descartado e os dados novos aparecem na interação
seguinte. O prazo de 24 horas continua valendo como segurança.

