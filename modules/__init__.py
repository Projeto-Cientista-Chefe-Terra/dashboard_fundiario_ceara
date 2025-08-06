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
    render_view_grafico_interativo
)
from .mapa_predominancia import (
    preparar_dados,
    criar_mapa_contextual,
    render_view_predominancia_map
)

from .mapa_assentamento import (
    render_view_assentamento_map
)

from .mapa_interativo import (
    render_view_mapa_interativo
)


from .mapa_gini import (
    render_view_gini_map
)

from .mapa_reservatorios import (
    render_view_reservatorios_map
)

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
    
    
    # Contextual map functions
    "preparar_dados", 
    "criar_mapa_contextual",
    
    # Configuration
    "DATA_SERVICE_URL",
    
    # views
    "render_view_predominancia_map",
    "render_view_mapa_interativo",
    "render_view_grafico_interativo",
    "render_view_gini_map",
    "render_view_assentamento_map",
    "render_view_reservatorios_map"
]