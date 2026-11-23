import pandas as pd
import joblib
import logging
import typing
from pathlib import Path

from src.utils.exepciones import ErrorCargandoArterfacto

logger = logging.getLogger(__name__)

def predict(x_feature:pd.DataFrame, 
            scaler_path:str|None, 
            model_path:str,
            threshold:float|None=None) -> pd.Series:
    
    """
    Carga los artefactos de ML desde disco, escala la matriz de features
    si corresponde y retorna las etiquetas de predicción como Serie.

    Soporta dos modos de predicción:
        - Con threshold : usa predict_proba sobre la clase positiva (columna 1)
        y aplica el corte manual. Útil cuando el umbral por defecto de 0.5
        no es óptimo para el negocio.
        - Sin threshold : usa predict directamente, aplicando el umbral
        interno del modelo.

    Parameters
    ----------
    x_feature : pd.DataFrame
        Matriz de features lista para inferencia, con columnas en el orden
        exacto que espera el artefacto escalador/modelo.
    scaler_path : str | None
        Ruta al artefacto escalador serializado con joblib. Si es None,
        se asume que el modelo no requiere escalado (ej. modelos basados
        en árboles).
    model_path : str
        Ruta al artefacto del modelo serializado con joblib.
    threshold : float | None, optional
        Umbral de corte sobre la probabilidad de la clase positiva.
        Si se omite, se usa predict() con el umbral interno del modelo.

    Returns
    -------
    pd.Series
        Serie de enteros (0/1) con nombre 'Prediccion', donde 1 indica
        que el asociado aplica a la oferta.

    Raises
    ------
    ErrorCargandoArterfacto
        Si alguno de los artefactos no se encuentra en la ruta especificada
        o falla su deserialización.
    """
    # --- Importamos los artefactos --- #
    try:
        with open(model_path, 'rb') as f:
            model = joblib.load(f)
            logger.info('Modelo: %s\n'
                         'Correctamente Cargado', Path(model_path).stem)
        if scaler_path:
            with open(scaler_path, 'rb') as f:
                scaler = joblib.load(f)
                logger.info('Scaler: %s\n'
                            'Correctamente Cargado', Path(model_path).stem)
        else:
            logger.info('El modelo no requiere de Scaler')
    except FileNotFoundError as e:
        raise ErrorCargandoArterfacto(f'Artefacto no encontrado {e}') from e
    except Exception as e:
        raise ErrorCargandoArterfacto(f'Error cargando artefacto: {e}') from e
    
    # --- Se genera la predicción --- #
    
    if scaler_path:
        X = scaler.transform(x_feature)
    else:
        X = x_feature.values
    
    if threshold is not None:
    
        etiquetas = pd.Series(
            (model.predict_proba(X)[:, 1] >= threshold).astype(int),
            name='Prediccion'
        )
    else:
        etiquetas = pd.Series(
            model.predict(X),
            name= 'Prediccion'
        )
    
    logger.info(
        'Predicción realizada\n'
        'Oferta: %d\n'
        'Descartadas: %d',
        (etiquetas == 1).sum(), (etiquetas == 0).sum(),
    )
    
    return etiquetas

def build_output(base_inicial:pd.DataFrame, 
                 features:pd.DataFrame,
                 etiquetas:pd.Series,
                 proceso:typing.Literal['Mt','Inactivos'], 
                 ) -> tuple[pd.DataFrame,...]:
    
    """
    Construye los tres DataFrames de salida a partir de las predicciones del modelo.

    Opera en tres pasos:
        1. Adjunta las etiquetas a la matriz de features → df_scored.
        2. Genera un resumen estadístico agrupado por etiqueta → summary.
        3. Incorpora las etiquetas a la base original y filtra únicamente
        los registros con Prediccion == 1 → base_inicial depurada.

    Parameters
    ----------
    base_inicial : pd.DataFrame
        DataFrame original (ej. tbl_factura) con todos los campos del negocio
        y la columna ASO_IDENTIFICACION como clave de join.
    features : pd.DataFrame
        Matriz de features post-dropna, con ASO_IDENTIFICACION intacto.
        Comparte índice con `etiquetas` al ser resultado de final_matrix.
    etiquetas : pd.Series
        Serie de etiquetas (0/1) retornada por predict(), alineada por índice
        con `features`.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
        - df_scored    : features + columna Prediccion.
        - summary      : medias y moda agrupadas por etiqueta.
        - base_inicial : base original filtrada a Prediccion == 1,
                        sin la columna Prediccion.
    """
    
    # --- Validacion proceso --- #
    
    if proceso not in ['Mt', 'Inactivos']:
        raise ValueError(
        f"proceso debe ser 'Mt' o 'Inactivos'. "
        f"Recibido: '{proceso}'"
        )
    
    # --- Nos traemos las etiquetas al df_original --- #
    
    df_scored = (
        pd.concat(
            objs=[features, etiquetas], 
            axis=1, 
        )
    )
    
    # --- Resumen Final --- #
    
    if proceso == 'Mt':
    
        summary = (
            df_scored
            .groupby(
                by='Prediccion', 
                as_index=False
            )
            .agg(
                Qasociados = ('ASO_IDENTIFICACION','count'), 
                media_productos = ('suma_productos','mean'), 
                media_antiguedad = ('antiguedad_anios','mean'),
                media_ingresos = ('ingresos','mean'),
                media_aportes = ('saldo_aportes','mean'),
                Moda_Perfil = ('strAgrupacionPerfil', lambda x: x.mode()[0])
            )
        )
    else:
        num_columns = [
            c for c in (df_scored
                        .select_dtypes('number')
                        .columns)
            if  c not in ['CEDULA','Prediccion']
        ]
        
        cat_columns = [
            c for c in df_scored.columns
            if c not in num_columns and
            c != 'CEDULA'
        ]
        
        summary = (
            pd.concat([
                (df_scored
                .groupby('Prediccion')
                .size()
                .reset_index(name='Conteo')), 
                (df_scored
                 .groupby('Prediccion')
                 [num_columns]
                 .mean()
                 .reset_index(drop=True)), 
                (df_scored
                 .groupby('Prediccion')
                 [cat_columns]
                 .agg(lambda c: c.mode().iloc[0] if not c.mode().empty else None)
                 .reset_index(drop=True))
            ], 
            axis=1)
        )
        
    # --- merge labels into original base --- #
    
    id_col = 'ASO_IDENTIFICACION' if proceso == 'Mt' else 'CEDULA'

    base_inicial = (
        pd.merge(
            left=base_inicial,
            right=df_scored[[id_col, 'Prediccion']],
            how='inner',
            on=id_col,
        )
        .loc[
            lambda df: df['Prediccion'] == 1,
            lambda df: [c for c in df.columns if c != 'Prediccion']
        ]
    )

    return df_scored, summary, base_inicial

def formatear_salida(
    base_inicial:pd.DataFrame, 
    proceso:typing.Literal['Mt','Inactivos'], 
) -> dict[str,pd.DataFrame]:
    
    """
    Persiste los resultados del modelo en la capa Gold del proyecto y,
    opcionalmente, en una ruta externa de red o directorio compartido.

    Escribe dos archivos en data/output/YYYYMM/<proceso>/:
        - predicciones.xlsx : dos hojas — 'BD' con la matriz de features
        y etiquetas, 'Summary' con métricas agregadas por etiqueta.
        - base_oferta.xlsx  : base original filtrada a Prediccion == 1,
        lista para el equipo comercial.

    Si se indica out_path, replica únicamente base_oferta.xlsx en esa ruta
    bajo la misma estructura YYYYMM/<proceso>/.

    Parameters
    ----------
    df_scored : pd.DataFrame
        Matriz de features con la columna Prediccion adjunta.
    summary : pd.DataFrame
        Resumen estadístico agrupado por etiqueta (output de build_output).
    base_inicial : pd.DataFrame
        Base original filtrada a los asociados con Prediccion == 1.
    proceso : Literal['Mt', 'Inactivos']
        Nombre del proceso. Determina la subcarpeta de destino y
        debe ser exactamente 'Mt' o 'Inactivos'.
    out_path : str | None, optional
        Ruta externa donde replicar base_oferta.xlsx. Si es None,
        solo se escribe en data/output/.

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con una sola clave — 'Moras' o 'Inactivos' según
        `proceso` — y como valor el subconjunto de base_inicial con
        ASO_IDENTIFICACION (o CEDULA), NOMBRE_ASOCIADO y
        PORCENTAJE_CONDONACION. Pensado para que el orquestador del
        pipeline lo retorne tal cual y se pueda mergear directo en
        `outputs` (ver `consolidar_ofertas`).

    Raises
    ------
    ValueError
        Si proceso no es 'Mt' ni 'Inactivos'.
    ErrorExportando
        Si falla la creación de directorios o la escritura de archivos.
    """

    if proceso not in {'Mt', 'Inactivos'}:
        raise ValueError(
            f"proceso debe ser 'Mt' o 'Inactivos'. "
            f"Recibido: '{proceso}'"
        )
    
    if proceso == 'Mt':
        columnas_salida = ['ASO_IDENTIFICACION', 'NOMBRE_ASOCIADO', 'PORCENTAJE_CONDONACION']
        etiqueta = 'Moras'
    else:
        
        # --- El else envia siempre a inactivos --- #
        ## --- Crear columna PORCENTAJE_CONDONACION --- ##
        
        base_inicial['PORCENTAJE_CONDONACION'] = 0.5
        columnas_salida = ['CEDULA', 'NOMBRE_ASOCIADO', 'PORCENTAJE_CONDONACION']
        etiqueta = 'Inactivos'

    return {etiqueta:base_inicial[columnas_salida]}