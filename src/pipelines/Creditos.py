import pandas as pd
from src.extraccion.creditos import extract_creditos
from src.transformacion.Creditos import (
    preparar_creditos, preparar_condonaciones, 
    preparar_alivio_previo, construir_asignacion_inicial, 
    enriquecer_asignacion, calcular_alivio_financiero, 
    aplicar_ranking_unico, 
)

def run_creditos(
    cfg:dict[str,dict],
    common_files:dict[str,pd.DataFrame]
) -> dict[str,pd.DataFrame]:

    """
    Orquesta el pipeline completo de Créditos: extracción, preparación
    de cartera y de los históricos de condonaciones/alivio previo,
    cálculo de ALIVIO_FINANCIERO y priorización de una sola oferta por
    asociado.

    Retorna la oferta envuelta en un diccionario (clave 'Creditos') en
    vez de un DataFrame plano, para que `consolidar_ofertas` (en
    `transformacion/consolidado_final.py`) pueda combinar los 3
    procesos del proyecto bajo una interfaz uniforme.

    Parameters
    ----------
    cfg : dict[str, dict]
        Configuración global del proyecto (`load_config()`), con las
        claves 'queries' y 'paths_creditos'.
    common_files : dict[str, pd.DataFrame]
        Insumos comunes ya extraídos (`extract_commons`); acá solo se
        usa 'Demografica' (antigüedad del asociado).

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con clave 'Creditos' y la base de oferta final
        (ASO_IDENTIFICACION, ASO_NOMBRE_COMPLETO, LLAVE,
        PORCENTAJE_CONDONACION), lista para consolidar con los otros
        procesos.
    """

    print('  → Extrayendo archivos Creditos...')
    files = extract_creditos(
        creditos_query=cfg['queries']['creditos'], 
        paths=cfg['paths_creditos'],
    )
    
    print('  → Transformando bases necesarias...')
    creditos = preparar_creditos(
        creditos_raw=files['Creditos'], 
    )
    condonaciones = preparar_condonaciones(
        condonaciones_raw=files['condonaciones'], 
    )
    alivio = preparar_alivio_previo(
        alivio_raw=files['alivio_previo'], 
    )
    
    print('  → Creando Base Ofrecimiento Inicial...')
    
    asignacion = enriquecer_asignacion(
        asignacion_inicial=construir_asignacion_inicial(
            creditos=creditos, 
            demografica=common_files['Demografica'], 
        ), 
        condonaciones=condonaciones, 
        alivio_previo=alivio, 
    )
    
    asignacion = calcular_alivio_financiero(
        asignacion=asignacion, 
    )
    
    print('  → Implementando filtro priorizacion...')
    base_oferta = aplicar_ranking_unico(
        asignacion=asignacion, 
    )

    return base_oferta