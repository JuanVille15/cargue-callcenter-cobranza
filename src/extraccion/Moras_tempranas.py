import pandas as pd
from src.conexion.gcc import execute_query
from src.utils.helpers import exportar, extract_files
from src.conexion.blob import leer_fuente

COLUMNAS_FAC = [
'ASO_IDENTIFICACION', 'CON_CODIGO', 'FACT_VALOR_VENCIDO'
]

def extract_fac_blob(fecha: str, conceptos: list[str]) -> pd.DataFrame:
    """Equivalente a facturaMT.sql, leyendo del lake. Solo las columnas que usa create_fac_base."""
    return leer_fuente(
        "STG_GCC_FACTURACION", fecha,
        columnas=COLUMNAS_FAC,
        filtro=lambda b: b[b["CON_CODIGO"].isin(conceptos)],
    )

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

def extract_MT(cfg: dict, fecha: str) -> dict[str, pd.DataFrame]:
    """
    Insumos de Moras Tempranas. Devuelve siempre las mismas claves
    ('fac', 'perseverados') sin importar el origen.
    """
    if cfg["origen"] == "blob":
        fac = extract_fac_blob(fecha, cfg["params"]["conceptos_mt"])
        files = {
            "perseverados": leer_fuente("PERSEVERADOS", fecha, columnas=["Identificacion"]),
        }
    else:
        fac = extract_fac(cfg["queries"]["factura_mt"])
        files = extract_files(configs=cfg["paths_mt"])
        files = exportar(fac=fac, files=files)

    files["fac"] = fac
    return files