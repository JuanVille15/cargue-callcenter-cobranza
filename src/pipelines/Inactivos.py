import pandas as pd
from src.extraccion.inactivos import extract_inactivos
from src.Model.inferencia import predict, build_output, export
from src.transformacion.Inactivos import (
    unir_alivios, agr_cuotas_pagadas, cruce_general,
    build_final_base,
)
from src.Model.Inactivos.build_df import (
    serie_oferta_inicial, perfil_vinculacion, vista_360,
    reactivaciones_previas, cruce_bases, final_matrix,
)

def run_inactivos(cfg: dict,
                  common_files:dict[str, pd.DataFrame]) -> dict[str,pd.DataFrame]:

    """
    Orquesta el pipeline completo de Inactivos: extracción, cruce
    contra alivios previos, feature engineering, inferencia del modelo
    de permanencia y persistencia de la oferta final.

    Retorna la oferta envuelta en un diccionario (clave 'Inactivos') en
    vez de un DataFrame plano, para que `consolidar_ofertas` (en
    `transformacion/consolidado_final.py`) pueda combinar los 3
    procesos del proyecto bajo una interfaz uniforme.

    Parameters
    ----------
    cfg : dict
        Configuración global del proyecto (`load_config()`), con las
        claves 'paths_inactivos', 'columnas', 'artifacts_inactivos' y
        'out_path_inactivos'.
    common_files : dict[str, pd.DataFrame]
        Insumos comunes ya extraídos (`extract_commons`): alivio,
        alivio_sp, r10, Perfil, vista_360, consol_inactivos.

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con clave 'Inactivos' y la base de oferta final
        (asociados con Prediccion == 1), lista para consolidar con los
        otros procesos.
    """

    print(' → Extrayendo archivos Inactivos...')

    inac_files = extract_inactivos(
        paths=cfg['paths_inactivos'],
    )

    print('  → Gerando Base Oferta Inicial Inactivos')
    base_alivios = unir_alivios(
        alivio=common_files['alivio'],
        alivio_sp=common_files['alivio_sp'],
    )
    tbl_cuotas_pagadas = agr_cuotas_pagadas(
        common_files['r10'],
    )
    oferta_inicial = cruce_general(
        Base_alivios=base_alivios,
        tbl_cuotas_pagadas=tbl_cuotas_pagadas,
        inactivos_files=inac_files,
    )
    oferta_inicial = build_final_base(
        base_final=oferta_inicial,
    )

    print('  → Construyendo DataFrame de features...')
    features = serie_oferta_inicial(
        oferta_inactivos=oferta_inicial,
    )
    features = cruce_bases(
        oferta_inactivos=features,
        perfil=perfil_vinculacion(perfil=common_files['Perfil']),
        vista360=vista_360(vista360=common_files['vista_360'],
                           ini_cols=cfg['columnas']['vista360_iniciales'],
                           rename_map=cfg['columnas']['renombres_vista360'],
                           output_cols=cfg['columnas']['vista360_finales']),
        reactivaciones=reactivaciones_previas(common_files['consol_inactivos'],
                                              )
    )

    x_features, features = final_matrix(
        base_final=features,
        col_order=cfg['columnas']['features_inactivos']
    )

    print('  → Aplicando modelo de permanencia...')
    etiquetas = predict(x_feature=x_features, 
                        scaler_path=cfg['artifacts_inactivos']['scaler'], 
                        model_path=cfg['artifacts_inactivos']['model'], 
                        )

    df_scored, summary, base_inicial = build_output(oferta_inicial, 
                                                    features=features, 
                                                    etiquetas=etiquetas, 
                                                    proceso='Inactivos')
    
    base_oferta_inactivos = export(
        df_scored=df_scored, 
        summary=summary, 
        base_inicial= base_inicial, 
        proceso='Inactivos', 
        out_path=cfg.get('out_path_inactivos', None)
    )

    return base_oferta_inactivos