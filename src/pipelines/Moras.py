import pandas as pd
from src.extraccion.Moras_tempranas import extract_MT
from src.transformacion.Moras_tempranas import (
    filtrar_r10, filtrar_aliviosp, filter_aliviofinanciero,
    filter_perseverados, cruzar_poblacion, create_fac_base,
    create_final_base, filter_acr,
)
from src.Model.Mt.build_df import (
    build_ini_base, demo_columns, cantidad_reactivaciones,
    perfil_asociado, final_matrix,
)
from src.Model.inferencia import predict, build_output, export

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
    print('  → Extrayendo archivos MT...')
    files = extract_MT(cfg, fecha)
    
    print('  → Filtrando y cruzando población R10...')
    r10 = filtrar_r10(common_files['r10'])
    r10 = cruzar_poblacion(r10, filtrar_aliviosp(common_files['alivio_sp']))
    r10 = cruzar_poblacion(r10, filter_aliviofinanciero(common_files['alivio']))
    r10 = cruzar_poblacion(r10, filter_acr(files['acr']))
    r10 = cruzar_poblacion(r10, filter_perseverados(files['perseverados']))
    tbl_factura = create_fac_base(r10, files['fac'])
    tbl_factura = create_final_base(tbl_factura, cfg['columnas']['alivio_mt'])

    print('  → Construyendo DataFrame de features...')
    alivio = build_ini_base(tbl_factura)
    alivio = demo_columns(alivio, common_files['Demografica'], cfg['columnas']['demo_mt'])
    alivio = cantidad_reactivaciones(common_files['consol_inactivos'], alivio)
    alivio = perfil_asociado(common_files['Perfil'], alivio)
    x_feature, alivio = final_matrix(alivio, cfg['columnas']['mt_feature_order'])

    print('  → Aplicando modelo de permanencia...')
    etiquetas = predict(x_feature, cfg['artifacts_mt']['scaler'], cfg['artifacts_mt']['model'], cfg.get('threshold_mt'))
    df_scored, summary, base_inicial = build_output(tbl_factura, alivio, etiquetas, proceso='Mt')
    base_oferta = export(df_scored, summary, base_inicial, proceso='Mt', out_path=cfg.get('out_path_mt', None))

    return base_oferta
