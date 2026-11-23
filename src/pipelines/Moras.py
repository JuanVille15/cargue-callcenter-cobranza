import pandas as pd
import logging
from src.conexion.blob import guardar_salida
from src.extraccion.Moras_tempranas import extract_MT
from src.transformacion.Moras_tempranas import (
    filtrar_r10,create_fac_base,
    create_final_base,
)
from src.Model.Mt.build_df import (
    build_ini_base, demo_columns, cantidad_reactivaciones,
    perfil_asociado, final_matrix,
)
from src.Model.inferencia import formatear_salida, predict, build_output
from src.transformacion.alternativas import cedulas_excluidas

logger = logging.getLogger(__name__)

def run_moras(cfg: dict, common_files: dict, fecha: str) -> dict[str,pd.DataFrame]:

    """
    Orquesta el pipeline completo de Moras Tempranas: extracción, cruce
    de población, feature engineering, inferencia del modelo de
    permanencia y persistencia de la oferta final.

    Retorna la oferta envuelta en un diccionario (clave 'Moras') en vez
    de un DataFrame plano, para que `consolidar_ofertas` (en
    `transformacion/consolidado_final.py`) pueda combinar los 3
    procesos del proyecto bajo una interfaz uniforme.

    Parameters
    ----------
    cfg : dict
        Configuración global del proyecto (`load_config()`), con las
        claves 'queries', 'paths_mt', 'columnas', 'artifacts_mt',
        'threshold_mt' y 'out_path_mt'.
    common_files : dict
        Insumos comunes ya extraídos (`extract_commons`): r10, alivio,
        alivio_sp, Demografica, consol_inactivos, Perfil.

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con clave 'Moras' y la base de oferta final
        (asociados con Prediccion == 1), lista para consolidar con los
        otros procesos.
    """
    logger.info('Extrayendo fuentes de Moras Tempranas...')
    files = extract_MT(cfg, fecha)
    
    logger.info('Filtrando y cruzando población R10...')
    r10 = filtrar_r10(common_files['r10'])
    excluidas = cedulas_excluidas(common_files["exclusiones"], cfg["exclusiones"]["moras"])
    antes = len(r10)
    r10 = r10.loc[~r10["CEDULA_ASOCIADO"].isin(excluidas)]
    logger.info("Moras: %d excluidos por alivios previos (%d -> %d)", antes - len(r10), antes, len(r10))
    tbl_factura = create_fac_base(r10, files['fac'])
    tbl_factura = create_final_base(tbl_factura, cfg['columnas']['alivio_mt'])
    guardar_salida(tbl_factura, "silver", "moras_poblacion", fecha)

    logger.info('Construyendo DataFrame de features...')    
    alivio = build_ini_base(tbl_factura)
    alivio = demo_columns(alivio, common_files['Demografica'], cfg['columnas']['demo_mt'])
    alivio = cantidad_reactivaciones(common_files['consol_inactivos'], alivio)
    alivio = perfil_asociado(common_files['Perfil'], alivio)
    x_feature, alivio = final_matrix(alivio, cfg['columnas']['mt_feature_order'])

    logger.info('Aplicando modelo de permanencia...')
    etiquetas = predict(x_feature, cfg['artifacts_mt']['scaler'], cfg['artifacts_mt']['model'], cfg.get('threshold_mt'))
    df_scored, summary, base_inicial = build_output(tbl_factura, alivio, etiquetas, proceso='Mt')
    guardar_salida(df_scored, "silver", "moras_predicciones", fecha)
    guardar_salida(base_inicial, "gold", "moras_ofertas", fecha)
    guardar_salida(summary, "gold", "sum_predicciones_moras", fecha)
    
    return formatear_salida(base_inicial, proceso='Mt')
