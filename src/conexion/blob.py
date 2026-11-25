"""
Lectura de insumos desde Blob Storage.

- En local se conecta a Azurite (DATA_STORAGE_CONNECTION_STRING).
- En Azure se conecta a la cuenta real con la identidad administrada
  (DATA_ACCOUNT_URL + DefaultAzureCredential), sin claves.

Qué archivos existen, con qué columnas y tipos, lo define config/fuentes.yaml.
"""

import logging
import os
import tempfile
from typing import Callable
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml
from azure.core.exceptions import ResourceNotFoundError, AzureError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient

from src.utils.exepciones import (
    CatalogoInvalidoError,
    InsumoNoEncontradoError,
    InsumosIncompletosError,
    SalidaNoGuardadaError, 
)

logger = logging.getLogger(__name__)

RUTA_CATALOGO = Path(__file__).resolve().parents[2] / "config" / "fuentes.yaml"
TIPOS_PERMITIDOS = {"Int64", "float64", "string", "category", "boolean"}
CLAVES_PERMITIDAS = {"archivo", "columnas", "dtype", "fechas", "requerido", "separador", "decimal" ,"decimal_coma"}

filtro = Callable[[pd.DataFrame], pd.DataFrame]

# ===============================
# CATALOGO
# ===============================

def _validar_catalogo(cat: dict) -> None:
    """Detecta errores del YAML que no rompen la sintaxis pero sí la lectura."""
    if "prefijo" not in cat or "fuentes" not in cat:
        raise CatalogoInvalidoError("fuentes.yaml debe tener 'prefijo' y 'fuentes'")

    for nombre, spec in cat["fuentes"].items():
        if not isinstance(spec, dict) or "archivo" not in spec:
            raise CatalogoInvalidoError(f"{nombre}: falta 'archivo'")

        extra = set(spec) - CLAVES_PERMITIDAS
        if extra:
            raise CatalogoInvalidoError(f"{nombre}: claves desconocidas {sorted(extra)} (¿sangría?)")

        columnas = spec.get("columnas")
        for col, tipo in (spec.get("dtype") or {}).items():
            if tipo not in TIPOS_PERMITIDOS:
                raise CatalogoInvalidoError(f"{nombre}.{col}: tipo '{tipo}' no permitido")
            if columnas and col not in columnas:
                raise CatalogoInvalidoError(f"{nombre}.{col}: tiene dtype pero no está en columnas")

        for col in spec.get("fechas") or []:
            if columnas and col not in columnas:
                raise CatalogoInvalidoError(f"{nombre}.{col}: está en fechas pero no en columnas")
    

@lru_cache(maxsize=1)
def catalogo() -> dict:
    """Lee y valida config/fuentes.yaml una sola vez
    por proceso"""
    with open(RUTA_CATALOGO, encoding="utf-8") as f:
        cat = yaml.safe_load(f)
        _validar_catalogo(cat)
    
    return cat

def ruta_blob(fuente: str, fecha: str) -> str:
    """Ruta del blob de una fuente para una fecha (YYYY-MM-DDD)"""
    fuentes = catalogo()["fuentes"]
    if fuente not in fuentes:
        raise KeyError(f"La fuente '{fuente}' no esta definida en fuentes.yaml")
    prefijo = catalogo()["prefijo"].format(fecha=fecha)

    return f"{prefijo}/{fuentes[fuente]["archivo"]}"

# ===============================
# CATALOGO
# ===============================

@lru_cache(maxsize=None)
def contenedor(capa: str = "bronze") -> ContainerClient:
    """Cliente del contenedor de una capa del lake (bronze, silver, gold). Uno por capa y proceso."""
    
    nombre = os.environ[f"DATA_CONTAINER_{capa.upper()}"]
    cadena = os.environ.get("DATA_STORAGE_CONNECTION_STRING")

    if cadena:
        logger.info("Conectando a %s con cadena de conexión (local)", nombre)
        return ContainerClient.from_connection_string(cadena, container_name=nombre)
    
    logger.info("Conectando a %s en %s con DefaultAzureCredential", nombre, os.environ["DATA_ACCOUNT_URL"])
    return ContainerClient(
        account_url=os.environ["DATA_ACCOUNT_URL"],
        container_name=nombre,
        credential=DefaultAzureCredential()
    )

# ===============================
# CATALOGO
# ===============================

def leer_fuente(
    fuente: str,
    fecha: str,
    columnas: list[str] | None = None,
    filtro: filtro | None = None,
    chunksize: int = 250_000,
) -> pd.DataFrame:
    """
    Lee una fuente del catálogo y la devuelve como DataFrame.

    - columnas: subconjunto de columnas; por defecto, las del catálogo.
    - filtro:   función DataFrame -> DataFrame. Si se pasa, el archivo se lee
                por bloques de `chunksize` filas y solo se conserva lo filtrado.

    El formato de cada archivo (separador, columnas con coma decimal) sale del catálogo.
    El blob se descarga a un archivo temporal (no a memoria) y se borra al terminar.
    """
    spec = catalogo()["fuentes"][fuente]
    ruta = ruta_blob(fuente, fecha)
    usecols = columnas or spec.get("columnas")
    tipos = spec.get("dtype") or {}

    # Solo se piden tipos, fechas y conversiones de las columnas que se van a leer.
    coma = [c for c in (spec.get("decimal_coma") or []) if not usecols or c in usecols]
    dtype = {
        c: ("string" if c in coma else t)  # las de coma decimal se leen como texto y se convierten después
        for c, t in tipos.items()
        if not usecols or c in usecols
    }
    fechas = [c for c in (spec.get("fechas") or []) if not usecols or c in usecols]

    opciones = {
        "usecols": usecols,
        "dtype": dtype or None,
        "parse_dates": fechas or None,
        "encoding": "utf-8",
        "sep": spec.get("separador", ","),
    }

    logger.info("Leyendo %s desde %s", fuente, ruta)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete_on_close=False) as tmp:
        try:
            contenedor().download_blob(ruta).readinto(tmp)
        except ResourceNotFoundError as e:
            raise InsumoNoEncontradoError(f"No existe el insumo '{fuente}' en {ruta}") from e
        tmp.close()

        try:
            if filtro is None:
                df = pd.read_csv(tmp.name, **opciones)
            else:
                partes = [filtro(bloque) for bloque in pd.read_csv(tmp.name, chunksize=chunksize, **opciones)]
                df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=usecols)

            # Columnas que la fuente entrega con coma decimal ("7457781,81"), al tipo del catálogo.
            for c in coma:
                df[c] = pd.to_numeric(df[c].str.replace(",", ".", regex=False)).astype(tipos.get(c, "float64"))
        except (TypeError, ValueError, OverflowError) as e:
            raise ValueError(f"{fuente}: No coincide con fuentes.yaml ({e}).") from e

    # Quitar espacios de relleno (columnas CHAR de Oracle): "Inactivos  " -> "Inactivos"
    for col in df.columns:
        if isinstance(df[col].dtype, pd.StringDtype):
            df[col] = df[col].str.strip()
        elif isinstance(df[col].dtype, pd.CategoricalDtype):
            df[col] = df[col].astype("string").str.strip().astype("category")

    logger.info(
        "%s: %d filas, %.1f MB en memoria",
        fuente, len(df), df.memory_usage(deep=True).sum() / 1024**2,
    )
    return df
    
def validar_insumos(fecha: str, fuentes: list[str] | None = None) -> None:
    
    """
    Verifica que existan en el blob todos los insumos requeridos de la fecha.
    Lanza InsumosIncompletosError con la lista de los que faltan.
    """

    todas = catalogo()["fuentes"]
    nombres = fuentes or [f for f, spec in todas.items() if  spec.get("requerido", True)]
    
    esperados = {ruta_blob(f, fecha): f for f in nombres}
    prefijo = catalogo()["prefijo"].format(fecha=fecha)
    presentes = {b.name for b in contenedor().list_blobs(name_starts_with=prefijo)}
    
    faltantes = sorted(f for ruta, f in esperados.items() if ruta not in presentes)
    if faltantes:
        raise InsumosIncompletosError(
            f"Faltan {len(faltantes)} insumos del {fecha}: {faltantes}"
        )
    
    logger.info("Insumos del %s completos (%d archivos)", fecha, len(esperados))
    
def guardar_salida(
    df: pd.DataFrame,
    capa: str, 
    nombre: str, 
    fecha: str,
) -> str:
    
    """Escribe un DataFrame como parquet en alivio/{nombre}/fecha={fecha}/{nombre}.parquet.
    Sobrescribe si ya existe: reprocesar una fecha reemplaza su salida"""
    
    ruta = f"alivio/{nombre}/fecha={fecha}/{nombre}.parquet"
    datos = df.to_parquet(index=False)
    try:
        contenedor(capa).upload_blob(ruta, datos, overwrite=True)
    except ResourceNotFoundError as e:
        raise SalidaNoGuardadaError(
            f"No existe el contenedor de la capa '{capa}'."
        ) from e
    except AzureError as e:
        raise SalidaNoGuardadaError(f"No se pudo guardar {nombre} en {capa}/{ruta}: {e}") from e
    
    logger.info("%s guardado en %s/%s (%d filas)", nombre, capa, ruta, len(df))
    return ruta 