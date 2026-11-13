import logging

import pandas as pd

logger = logging.getLogger(__name__)
MOTIVOS_ESPERADOS = ("ACR", "ALIVIO_SP", "ALIVIO_MT", "PERSEVERADO")

def alternativas_vigentes(
    hist: pd.DataFrame, 
    procesos: list[str],
)-> pd.DataFrame:
    
    """Filtra historico alternativas: tabla de no aplica x alternativas"""

    return (
        hist.loc[hist["PROCESO_ORIGEN"].isin(procesos)]
    )

def clasificar_motivo(vigentes: pd.DataFrame) -> pd.Series:
    """
    Motivo de exclusión por alternativa:
    - Inactivos: los alivios son ALIVIO_SP; todo lo demás es ACR.
    - Activos:   los alivios son ALIVIO_MT; las que contienen 'ACR' (Anulación ACR) son ACR.
    Lo que no cumple ninguna regla no es motivo de exclusión (None).
    """
    alt = vigentes["ALTERNATIVA"]
    es_alivio = alt.str.contains("alivio", case=False, na=False)
    menciona_acr = alt.str.contains("ACR", case=False, na=False)
    inactivos = vigentes["PROCESO_ORIGEN"] == "Inactivos"
    activos = vigentes["PROCESO_ORIGEN"] == "Activos"

    return pd.Series(pd.NA, index=vigentes.index, dtype="string").case_when([
        (inactivos & es_alivio,    "ALIVIO_SP"),
        (inactivos & ~es_alivio,   "ACR"),
        (activos & es_alivio,      "ALIVIO_MT"),
        (activos & menciona_acr,   "ACR"),
    ])

def _registrar_resumen(tabla: pd.DataFrame) -> None:
    """Conteos por motivo: avisa si alguno esperado viene vacio"""
    conteo = tabla["MOTIVO"].value_counts()
    logger.info(
        "Exclusiones: %d filas, %d cedulas unicas. Por motivo: %s",
        len(tabla), tabla["CEDULA"].nunique(), conteo.to_dict()
    )
    
    vacios = [m for m in MOTIVOS_ESPERADOS if conteo.get(m, 0) == 0]
    if vacios:
        logger.warning("Motivos de exclusion sin registros: %s. Revisar HIST/PERSEVERADOS,", vacios)

def tabla_exclusiones(
    vigentes: pd.DataFrame, 
    perseverados: pd.DataFrame, 
) -> pd.DataFrame:
    
    """Una fila por (cedula, motivo) que impide ofrecer un alivio.
    Tabla de trazabilidad en silver."""
    
    clasificadas = vigentes.assign(MOTIVO=clasificar_motivo, FUENTE="GCC_HIST_ALTERNATIVAS")
    
    sin_motivo = clasificadas.loc[clasificadas["MOTIVO"].isna(), "PROCESO_ORIGEN"].value_counts()
    if not sin_motivo.empty:
        logger.info("Alternativas que no excluyen (se descartan), por proceso: %s", sin_motivo.to_dict())

    desde_hist = (
        clasificadas
        .dropna(subset=["MOTIVO"])
        .sort_values("FECHA_APLICACION", ascending=False, kind="stable")
        .drop_duplicates(subset=["ASO_IDENTIFICACION", "MOTIVO"])
        .rename(columns={"ASO_IDENTIFICACION": "CEDULA", "FECHA_APLICACION": "FECHA_EVENTO"})
        [["CEDULA", "MOTIVO", "FUENTE", "FECHA_EVENTO", "ALTERNATIVA", "PROCESO_ORIGEN"]]
    )
    
    desde_pers = (
        perseverados[["Identificacion"]]
        .drop_duplicates()
        .rename(columns={"Identificacion":"CEDULA"})
        .assign(
            MOTIVO="PERSEVERADO", 
            FUENTE="PERSEVERADOS", 
            FECHA_EVENTO= lambda df: pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]"),
        )
    )
    
    tabla = pd.concat([desde_hist, desde_pers], ignore_index=True)
    _registrar_resumen(tabla)
    
    return tabla