import pandas as pd
from src.utils.helpers import exportar, extract_files
from src.conexion.gcc import execute_query

def extract_creditos_sql(
    creditos_query:str,
) -> dict[str,pd.DataFrame]:

    """
    Ejecuta la consulta SQL de cartera de créditos cooperativos contra
    el DWH de GCC.

    Parameters
    ----------
    creditos_query : str
        Ruta al archivo SQL con la consulta de créditos (ver
        `cfg['queries']['creditos']`).

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con clave 'Creditos' y el DataFrame resultante.
    """
    print("Ejecutando querys GCC DWH")
    print(f"\nExtrayendo cartera creditos")
    creditos = execute_query(
        query=creditos_query,
    )

    return {'Creditos':creditos}

def extract_creditos(creditos_query:str,
                     paths:dict[str,dict]) -> dict[str,pd.DataFrame]:

    """
    Orquesta el proceso completo de extracción de insumos para Créditos.

    Ejecuta en secuencia:
        1. Extracción de la cartera de créditos desde el DWH GCC.
        2. Lectura de archivos Excel (condonaciones, alivio previo) vía
           el helper genérico `extract_files` (`src.utils.helpers`).
        3. Persistencia de todos los insumos en `data/raw/YYYYMM/`.

    La antigüedad del asociado no se extrae acá: ya viene resuelta en
    `common_files['Demografica']` (ver `extract_commons`), y se cruza
    en la etapa de transformación.

    Parameters
    ----------
    creditos_query : str
        Ruta al archivo SQL con la consulta de créditos.
    paths : dict[str, dict]
        Diccionario con la configuración de cada archivo Excel a procesar
        (ver `cfg['paths_creditos']` y `extract_files`).

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con todos los insumos del proceso indexados por
        nombre, listo para que la siguiente etapa (transformación)
        opere en memoria sin necesidad de releer los archivos.
    """
    # --- 1. Extraemos la cartera de creditos desde SQL --- #
    creditos = extract_creditos_sql(creditos_query=creditos_query)

    # --- 2. Extraemos archivos directos --- #
    files = extract_files(configs=paths)
    files.update(creditos)

    # --- 3. cargamos into raw --- #
    files = exportar(fac=None,
                     files=files)
    print("Bases Alivio Creditos Exportadas")

    return files