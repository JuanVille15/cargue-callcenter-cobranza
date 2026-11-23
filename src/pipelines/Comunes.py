import pandas as pd

from src.conexion.blob import validar_insumos, guardar_salida
from src.extraccion.commons import extract_common_blob
from src.transformacion.alternativas import alternativas_vigentes, tabla_exclusiones

def run_comunes(cfg: dict, fecha: str) -> dict[str, pd.DataFrame]:
    """Valida insumos, extrae los comunes del lake y arma tabla de exclusiones
    (La guarda tambien en SILVER)."""
    
    validar_insumos(fecha)
    comunes = extract_common_blob(fecha=fecha, cfg=cfg)
    vigentes = alternativas_vigentes(comunes["hist_alternativas"],  cfg["params"]["procesos_alternativas"])
    comunes["exclusiones"] = tabla_exclusiones(vigentes=vigentes, perseverados=comunes["perseverados"])
    guardar_salida(comunes["exclusiones"], "Silver", "exclusiones", fecha)

    return comunes