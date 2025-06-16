# modules/__init__.py

from .data_loader import (
    load_csv_data,
    load_municipios,
    validate_data
)
from .grafico_interativo import (
    filtrar_dados,
    classificar_propriedades,
    plot_barras,
    plot_pizza,
    compute_stats_df
)
from .mapa_contextual import (
    preparar_dados,
    criar_mapa_contextual
)
# from .mapa_interativo import (
#     preprocessar_tudo,
#     criar_mapa_com_camadas
# )

# Version of the modules package
__version__ = "1.0.0"

# API configuration (can be overridden by users)
DATA_SERVICE_URL = "http://localhost:8000"

__all__ = [
    # Data loading and validation
    "load_csv_data", 
    "load_municipios", 
    "validate_data",
    
    # Interactive chart functions
    "filtrar_dados", 
    "classificar_propriedades", 
    "plot_barras", 
    "plot_pizza", 
    "compute_stats_df",
    
    # Contextual map functions
    "preparar_dados", 
    "criar_mapa_contextual",
    
   
    # Configuration
    "DATA_SERVICE_URL"
]