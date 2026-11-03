import pandas as pd
from src.conexion.gcc import execute_query
from src.utils.helpers import exportar, extract_files

def extract_fac(Factura_MT_query:str) -> pd.DataFrame:

    """
    Ejecuta la consulta SQL de facturación de clientes estatutarios contra
    el DWH de GCC.

    La población R10 ya no se pide acá: se extrae una sola vez en
    `extract_commons` (GCC) y se reutiliza entre los pipelines que la
    necesitan (MT, Inactivos), en vez de consultarla por separado en
    cada uno.

    Parameters
    ----------
    Factura_MT_query : str
        Ruta o contenido de la consulta SQL para extraer la facturación estatutaria.

    Returns
    -------
    pd.DataFrame
        DataFrame con la facturación estatutaria.
    """
    print("Ejecutando querys GCC DWH")
    print(f"\nExtrayendo facturacion estatutarios")
    fac = execute_query(query=Factura_MT_query)

    return fac

def extract_MT(Factura_MT_query:str,
               paths:dict) -> dict[str,pd.DataFrame]:

    """
    Orquesta el proceso completo de extracción de insumos para Moras Tempranas.

    Ejecuta en secuencia:
        1. Extracción de la facturación desde el DWH GCC.
        2. Lectura de archivos Excel desde rutas locales.
        3. Persistencia de todos los insumos en `data/raw/YYYYMM/`.

    La población R10 no se extrae acá: ya viene resuelta en `common_files`
    (ver `extract_commons`), donde se pide una sola vez y se comparte entre
    los pipelines que la necesitan.

    Además de escribir a disco, retorna el diccionario consolidado de DataFrames
    para que la siguiente etapa del pipeline (transformación) opere en memoria
    sin necesidad de releer los archivos.

    Parameters
    ----------
    Factura_MT_query : str
        Ruta o contenido de la consulta SQL para extraer la facturación estatutaria.
    paths : dict
        Diccionario con los nombres y rutas de los archivos Excel a procesar.

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con todos los insumos del proceso indexados por nombre,
        incluyendo 'fac' además de los archivos locales.
    """

    # --- 1. Extraemos la factura desde SQL --- #
    fac = extract_fac(Factura_MT_query=Factura_MT_query)

    # --- 2. Extraemos archivos directos --- #
    files = extract_files(configs=paths)

    # --- 3. cargamos into raw --- #
    files = exportar(fac=fac,
                     files= files)
    print("Bases Alivio Moras Tempranas Exportadas✅")

    return files