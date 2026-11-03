import pandas as pd
from src.utils.helpers import exportar, extract_files

def extract_inactivos(paths: dict) -> dict[str, pd.DataFrame]:
    """
    Orquesta el proceso completo de extracción de insumos para Inactivos.

    Ejecuta en secuencia:
        1. Lectura de los archivos Excel indicados en `paths`, vía el
           helper genérico `extract_files` (`src.utils.helpers`). Como
           'poblacion_inactivos' y 'scoring' apuntan a carpetas, se
           resuelve automáticamente el archivo más reciente de cada una.
        2. Persistencia de todos los insumos en `data/raw/YYYYMM/` vía el
           helper compartido `exportar` (mismo usado por MT), que decide
           el formato de cada archivo según su volumen.

    A diferencia de MT, acá no hay extracción SQL propia: `r10` y
    `alivio_sp` ya vienen resueltos en `common_files` (ver
    `extract_commons`), por lo que este módulo solo se ocupa de los
    insumos exclusivos de Inactivos (población, scoring, alivios).

    Parameters
    ----------
    paths : dict
        Diccionario con la configuración de cada archivo Excel a procesar
        (ver `extract_files` en `src.utils.helpers`).

    Returns
    -------
    dict
        Diccionario con todos los insumos del proceso indexados por
        nombre, listo para que la siguiente etapa (transformación)
        opere en memoria sin necesidad de releer los archivos.
    """
    # --- 1. Extraemos files --- #
    files = extract_files(paths)
    
    # --- 2.Persistimos los archivos y retornamos --- #
    files = exportar(fac=None,
                     files=files, 
    )
    print('Bases Alivio Inactivos correctamente exportadas✅')
    return files