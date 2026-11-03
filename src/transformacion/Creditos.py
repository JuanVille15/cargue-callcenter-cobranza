import pandas as pd
import numpy as np
import janitor
import datetime
from pathlib import Path
from src.utils.exepciones import ErrorExportando

# ==================
# PREPARACION DATOS
# ==================

def preparar_creditos(
    creditos_raw:pd.DataFrame
) -> pd.DataFrame:

    """
    Prepara la cartera de créditos cooperativos: calcula la tasa efectiva,
    la edad de mora inicial (corregida contra cuotas atrasadas), las
    banderas de cláusula aceleratoria y cierre de obligación, normaliza
    las fechas y deduplica por obligación.

    Pasos aplicados:
        - Calcula TASA_EFECTIVA_ANUAL a partir de TASA_NOMINAL_ANUAL.
        - Calcula EDAD_DE_MORA_INI como el redondeo hacia arriba de
          FACT_DIAS_DE_MORA / 30 (equivalente al `cut()` en tramos de 30
          días del script R), y la corrige contra CUOTAS_ATRASADAS: si el
          tramo calculado queda por debajo de CUOTAS_ATRASADAS, o justo 1
          por encima, se pisa con CUOTAS_ATRASADAS.
        - Calcula CLAUSULA_ACELERATORIA y CIERRE_OBLIGACION a partir de
          SALDO_TOTAL, VENCIDO_TOTAL, EDAD_DE_MORA_INI (ya corregida),
          CUOTAS_ATRASADAS y CUOTAS_PENDIENTES.
        - Normaliza a datetime las columnas ASO_FECHA_CAMBIO_ESTADO_MULT,
          FECHA_DESEMBOLSO y FECHA_CIERRE (`errors='coerce'`: fechas
          inválidas quedan en NaT en vez de romper el proceso).
        - Construye LLAVE a partir de PAGARE, reemplazando el último
          dígito por '0', para agrupar todas las versiones/renovaciones
          de una misma obligación bajo una sola clave.
        - Deduplica por (ASO_IDENTIFICACION, LLAVE): de todas las
          versiones de un mismo crédito, conserva únicamente la fila que
          sea a la vez la versión más reciente (version == max(version))
          y la de menor mora (FACT_DIAS_DE_MORA == min(FACT_DIAS_DE_MORA))
          dentro del grupo. Si ninguna fila cumple ambas condiciones a la
          vez, el grupo completo se pierde (mismo comportamiento que el
          `filter()` original en R).

    Parameters
    ----------
    creditos_raw : pd.DataFrame
        DataFrame crudo con la cartera de créditos cooperativos, resultado
        de `extract_creditos_sql` (ver `extraccion/creditos.py`).

    Returns
    -------
    pd.DataFrame
        DataFrame de créditos con una fila por obligación (LLAVE) y por
        asociado, con las columnas derivadas (TASA_EFECTIVA_ANUAL,
        EDAD_DE_MORA_INI corregida, CLAUSULA_ACELERATORIA,
        CIERRE_OBLIGACION, LLAVE) y fechas normalizadas.
    """
    
    # --- Creacion de columnas --- #
    
    ## --- TASA_EFECTIVA_ANUAL y EDAD_MORA_INICIAL --- ##
    creditos = (
        creditos_raw
        .dropna(
            subset=['FACT_DIAS_DE_MORA'], 
            axis=0, 
            ignore_index=True, 
        )
        .assign(
            tasa_nominal_decimal = (
                creditos_raw['TASA_NOMINAL_ANUAL'] / 100
            ), 
            TASA_EFECTIVA_ANUAL = lambda df:
                ((1 + (df['tasa_nominal_decimal']/12))**12 - 1).mul(100), 
            EDAD_DE_MORA_INI = lambda df:
                np.ceil(df['FACT_DIAS_DE_MORA'] / 30).astype(int), 
            EDAD_MORA_INI = lambda df:
                np.where(
                    (df['EDAD_DE_MORA_INI'] < df['CUOTAS_ATRASADAS']) | (df['EDAD_DE_MORA_INI'] - df['CUOTAS_ATRASADAS'] == 1), 
                    df['CUOTAS_ATRASADAS'], 
                    df['EDAD_DE_MORA_INI']
                )
        )
        .drop(
            columns= ['tasa_nominal_decimal','EDAD_DE_MORA_INI'], 
        )
        .rename(
            columns={
             'EDAD_MORA_INI': 'EDAD_DE_MORA_INI'
            }
        ) 
    )
    
    ## --- CLAUSULA_ACELERATORIA: CIERRE OBLIGACION --- ##
    
    creditos = (
        creditos
        .assign(
            CLAUSULA_ACELERATORIA = np.where(
                ((creditos['SALDO_TOTAL'] - creditos['VENCIDO_TOTAL'] <= 10_000) &
                (creditos['EDAD_DE_MORA_INI'] > creditos['CUOTAS_ATRASADAS']) &
                (creditos['CUOTAS_ATRASADAS'] < creditos['CUOTAS_PENDIENTES'])),
                1,
                0
            ),
            CIERRE_OBLIGACION = np.where(
                ((creditos['SALDO_TOTAL'] - creditos['VENCIDO_TOTAL'] <= 10_000) &
                (creditos['EDAD_DE_MORA_INI'] >= creditos['CUOTAS_ATRASADAS']) &
                (creditos['CUOTAS_ATRASADAS'] == creditos['CUOTAS_PENDIENTES'])),
                1,
                0
            ), 
        )
    )
    
    # --- Se aseguran tipos: Columnas DateTime --- #
    
    creditos = (
        creditos
        .assign(
            ASO_FECHA_CAMBIO_ESTADO_MULT = pd.to_datetime(
                creditos['ASO_FECHA_CAMBIO_ESTADO_MULT'], 
                errors='coerce', 
            ), 
            FECHA_DESEMBOLSO = pd.to_datetime(
                creditos['FECHA_DESEMBOLSO'], 
                errors='coerce', 
            ), 
            FECHA_CIERRE = pd.to_datetime(
                creditos['FECHA_CIERRE'], 
                errors='coerce', 
            ),
        )
    )
    
    # --- Se evitan duplicados: Por veresion y edad de mora --- #
    
    creditos = (
        creditos
        .assign(
            LLAVE = (
                creditos['PAGARE']
                .astype(str)
                .str[:-1] + '0'
            ).astype(int),  
            version = (
                creditos['PAGARE']
                .astype(str)
                .str[-2:]
            ).astype(int), 
            max_version = lambda df:
                df.groupby(
                    by = ['ASO_IDENTIFICACION','LLAVE']
                )['version'].transform('max'), 
            min_mora = lambda df:
                df.groupby(
                    by=['ASO_IDENTIFICACION', 'LLAVE']
                )['FACT_DIAS_DE_MORA'].transform('min')
        )
        .loc[
            (lambda df: 
                (df['version'] == df['max_version']) & 
                (df['FACT_DIAS_DE_MORA'] == df['min_mora'])
            ), 
            lambda df: 
                [c for c in df.columns if c not in ('version', 'max_version', 'min_mora')]
        ]
    )

    return creditos

def preparar_condonaciones(condonaciones_raw:pd.DataFrame) -> pd.DataFrame:

    """
    Normaliza el consolidado de condonaciones y lo reduce a una fila por
    LLAVE, quedándose con la condonación más reciente de cada crédito.

    Pasos aplicados:
        - Normaliza nombres de columnas vía `janitor.clean_names`.
        - Construye LLAVE a partir de NUMERO_CREDITO: si tiene 8 dígitos,
          reemplaza el último por '0'; si tiene otra longitud, reemplaza
          los últimos 2 por '00'. Es una regla distinta a la de `LLAVE`
          en `preparar_creditos` (que siempre pisa 1 solo dígito) porque
          acá NUMERO_CREDITO no siempre viene con 8 dígitos.
        - Se queda con LLAVE y FECHA_CONDONACION, y por cada LLAVE
          conserva solo la fila con la FECHA_CONDONACION más reciente
          (la primera en caso de empate, igual que `which.max()` en R).

    Parameters
    ----------
    condonaciones_raw : pd.DataFrame
        DataFrame crudo leído desde 'Consolidado condonaciones.xlsx'
        (hoja 'DATA').

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas LLAVE y FECHA_CONDONACION, una fila por
        crédito con condonación aplicada.
    """
    condonaciones = janitor.clean_names(
        df=condonaciones_raw,
        case_type='upper',
        strip_accents=True,
    )

    numero_credito = condonaciones['NUMERO_CREDITO'].astype('Int64').astype(str)

    condonaciones = (
        condonaciones
        .assign(
            LLAVE = np.where(
                numero_credito.str.len() == 8,
                numero_credito.str[:7] + '0',
                numero_credito.str[:8] + '00'
            ).astype(int)
        )
        [['LLAVE', 'FECHA_CONDONACION']]
        .sort_values(
            by='FECHA_CONDONACION',
            ascending=False,
            kind='stable',
        )
        .drop_duplicates(
            subset='LLAVE',
            keep='first',
        )
    )

    return condonaciones

def preparar_alivio_previo(alivio_raw:pd.DataFrame) -> pd.DataFrame:

    """
    Normaliza el histórico de alivios financieros ya aplicados y lo
    reduce a una fila por LLAVE, quedándose con la aplicación más
    reciente de cada crédito.

    Pasos aplicados:
        - Normaliza nombres de columnas vía `janitor.clean_names`.
        - Filtra únicamente los registros con ESTADO == 'APLICADO'.
        - Construye LLAVE a partir de NUMERO_DE_CREDITO (misma regla
          condicional por longitud que en `preparar_condonaciones`).
        - Se queda con LLAVE y PERIODO (renombrada a FECHA_APLICACION),
          y por cada LLAVE conserva solo la fila con la
          FECHA_APLICACION más reciente (la primera en caso de empate).

    Parameters
    ----------
    alivio_raw : pd.DataFrame
        DataFrame crudo leído desde 'Definitivo_Validado_Consolidado.xlsx'
        (histórico de alivios financieros de créditos).

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas LLAVE y FECHA_APLICACION, una fila por
        crédito con alivio ya aplicado.
    """
    alivio = (
        janitor.clean_names(
            df=alivio_raw,
            case_type='upper',
            strip_accents=True,
        )
        .loc[lambda df: df['ESTADO'] == 'APLICADO']
    )

    numero_credito = alivio['NUMERO_DE_CREDITO'].astype('Int64').astype(str)

    alivio = (
        alivio
        .assign(
            LLAVE = np.where(
                numero_credito.str.len() == 8,
                numero_credito.str[:7] + '0',
                numero_credito.str[:8] + '00'
            ).astype(int)
        )
        .rename(
            columns={'PERIODO': 'FECHA_APLICACION'}
        )
        [['LLAVE', 'FECHA_APLICACION']]
        .sort_values(
            by='FECHA_APLICACION',
            ascending=False,
            kind='stable',
        )
        .drop_duplicates(
            subset='LLAVE',
            keep='first',
        )
    )

    return alivio

def construir_asignacion_inicial(creditos:pd.DataFrame,
                                 demografica:pd.DataFrame) -> pd.DataFrame:

    """
    Enriquece la cartera de créditos con la antigüedad del asociado,
    cruzando contra la vista demográfica común del proyecto (Bodega BI).

    A diferencia del script R (que trae ANTIGUEDAD desde una query propia
    contra GCC), acá se reutiliza `common_files['Demografica']` — ya
    extraída una sola vez para todos los procesos del proyecto (ver
    `extract_commons`) — porque ya trae `antiguedad_anios` calculada.
    EDAD, regional, zona, etc. no se traen porque no se usan en ninguna
    regla de alivio.

    Parameters
    ----------
    creditos : pd.DataFrame
        DataFrame de créditos, resultado de `preparar_creditos`.
    demografica : pd.DataFrame
        DataFrame demográfico común del proyecto (`common_files['Demografica']`),
        se asume una fila por Identificacion.

    Returns
    -------
    pd.DataFrame
        DataFrame de créditos enriquecido con ANTIGUEDAD.

    Raises
    ------
    ValueError
        Si `demografica` trae identificaciones duplicadas: el join
        dejaría de ser 1:1 y duplicaría créditos.
    """
    if demografica['Identificacion'].duplicated().any():
        raise ValueError(
            "common_files['Demografica'] trae identificaciones duplicadas; "
            "el join contra creditos dejaría de ser 1:1."
        )

    asignacion_inicial = (
        creditos
        .merge(
            right=demografica[['Identificacion', 'antiguedad_anios']],
            how='left',
            left_on='ASO_IDENTIFICACION',
            right_on='Identificacion',
        )
        .drop(columns='Identificacion')
        .rename(columns={'antiguedad_anios': 'ANTIGUEDAD'})
    )

    return asignacion_inicial

def enriquecer_asignacion(asignacion_inicial:pd.DataFrame,
                          condonaciones:pd.DataFrame,
                          alivio_previo:pd.DataFrame) -> pd.DataFrame:

    """
    Cruza la asignación inicial de créditos contra los históricos de
    condonaciones y alivios previamente aplicados, ambos por LLAVE.

    Del script R original se omiten a propósito los joins contra
    CUO_PA_APORTES, VECTOR (mora histórica) y HERRAMIENTAS: ninguno de
    los tres alimenta la regla de ALIVIO_FINANCIERO (ver mapeo de
    dependencias hecho antes), así que no hace falta extraerlos ni
    cruzarlos acá.

    Parameters
    ----------
    asignacion_inicial : pd.DataFrame
        Resultado de `construir_asignacion_inicial`.
    condonaciones : pd.DataFrame
        Resultado de `preparar_condonaciones` (LLAVE, FECHA_CONDONACION).
    alivio_previo : pd.DataFrame
        Resultado de `preparar_alivio_previo` (LLAVE, FECHA_APLICACION).

    Returns
    -------
    pd.DataFrame
        DataFrame enriquecido con FECHA_CONDONACION y FECHA_APLICACION.
    """
    asignacion = (
        asignacion_inicial
        .merge(
            right=condonaciones,
            how='left',
            on='LLAVE',
        )
        .merge(
            right=alivio_previo,
            how='left',
            on='LLAVE',
        )
    )

    return asignacion

def calcular_alivio_financiero(asignacion:pd.DataFrame) -> pd.DataFrame:

    """
    Calcula la oferta de ALIVIO_FINANCIERO por tramos de mora, según
    producto, antigüedad, cuotas pagadas/pendientes y el historial de
    condonaciones y alivios previos del crédito.

    Los cortes de fecha se recalculan cada corrida (relativos a
    `pd.Timestamp.today()`), igual que en el script R:
        - PERIODO_DESEM: créditos desembolsados hace más de 180 días.
        - PERIODO: sin condonación ni alivio previo en los últimos 365
          días (o nunca).

    Tramos evaluados en orden (gana el primero que matchea, vía
    `np.select` — mismo comportamiento que `case_when` en R):
        1. Mora > 60d, >= 6 cuotas pagadas, producto CRCUOINI/CRPATRIM,
           sin alivio previo aplicado nunca -> 'Aplica 50% - FG'.
        2-5. Mora en (60,90]/(90,120]/(120,150]/>150 días, antigüedad >= 2
           años, >= 24 cuotas pagadas, > 6 cuotas pendientes, producto en
           {CRESOLID, CREDIASO, CRCUOINI, REESTCRS, CRPATRIM}, sin alivio
           previo aplicado nunca -> 'Aplica 35/40/45/50% - Financiero'.
        - Si no matchea ninguno -> 'No Aplica'.

    No se calculan acá TIPO_MODIFICACION ni CONDONACION (las otras 2
    reglas del script R): no forman parte del alcance de la oferta de
    alivio financiero y dependen de insumos que este módulo no extrae
    (VECTOR de mora histórica, HERRAMIENTAS aplicadas).

    Parameters
    ----------
    asignacion : pd.DataFrame
        Resultado de `enriquecer_asignacion`.

    Returns
    -------
    pd.DataFrame
        Mismo DataFrame de entrada, con la columna ALIVIO_FINANCIERO
        agregada.
    
    Raises
    ------
    ErrorExportando
        Si falla la creación del directorio o la escritura del archivo
        en data/processed/.
    """
    periodo_desem = pd.Timestamp.today().normalize() - pd.Timedelta(days=180)
    periodo = pd.Timestamp.today().normalize() - pd.Timedelta(days=365)

    dias_mora = asignacion['FACT_DIAS_DE_MORA']
    desembolso_antiguo = asignacion['FECHA_DESEMBOLSO'] <= periodo_desem
    sin_condonacion_reciente = (
        (asignacion['FECHA_CONDONACION'] <= periodo) | asignacion['FECHA_CONDONACION'].isna()
    )
    sin_alivio_previo = asignacion['FECHA_APLICACION'].isna()

    productos_financiero = ['CRESOLID', 'CREDIASO', 'CRCUOINI', 'REESTCRS', 'CRPATRIM']

    condiciones = [
        (dias_mora > 60) &
        (asignacion['CUOTAS_PAGADAS'] >= 6) &
        desembolso_antiguo &
        asignacion['PRODUCTO'].isin(['CRCUOINI', 'CRPATRIM']) &
        sin_condonacion_reciente &
        sin_alivio_previo,

        (dias_mora > 60) & (dias_mora < 91) &
        (asignacion['ANTIGUEDAD'] >= 2) &
        (asignacion['CUOTAS_PAGADAS'] >= 24) &
        desembolso_antiguo &
        asignacion['PRODUCTO'].isin(productos_financiero) &
        sin_condonacion_reciente &
        sin_alivio_previo &
        (asignacion['CUOTAS_PENDIENTES'] > 6),

        (dias_mora > 90) & (dias_mora < 121) &
        (asignacion['ANTIGUEDAD'] >= 2) &
        (asignacion['CUOTAS_PAGADAS'] >= 24) &
        desembolso_antiguo &
        asignacion['PRODUCTO'].isin(productos_financiero) &
        sin_condonacion_reciente &
        sin_alivio_previo &
        (asignacion['CUOTAS_PENDIENTES'] > 6),

        (dias_mora > 120) & (dias_mora < 151) &
        (asignacion['ANTIGUEDAD'] >= 2) &
        (asignacion['CUOTAS_PAGADAS'] >= 24) &
        desembolso_antiguo &
        asignacion['PRODUCTO'].isin(productos_financiero) &
        sin_condonacion_reciente &
        sin_alivio_previo &
        (asignacion['CUOTAS_PENDIENTES'] > 6),

        (dias_mora > 150) &
        (asignacion['ANTIGUEDAD'] >= 2) &
        (asignacion['CUOTAS_PAGADAS'] >= 24) &
        desembolso_antiguo &
        asignacion['PRODUCTO'].isin(productos_financiero) &
        sin_condonacion_reciente &
        sin_alivio_previo &
        (asignacion['CUOTAS_PENDIENTES'] > 6),
    ]

    resultados = [
        '0.5',
        '0.35',
        '0.4',
        '0.45',
        '0.5',
    ]

    asignacion = asignacion.assign(
        ALIVIO_FINANCIERO = np.select(condiciones, resultados, default='No Aplica')
    )
    CREDITOS_APLICA = int(asignacion[asignacion['ALIVIO_FINANCIERO'] != 'No Aplica'].shape[0])
    print(f'Creditos Aplican Inicialmente: {CREDITOS_APLICA}')

    # --- Persiste en Processed (Silver) --- #

    BASE_PATH = Path(__file__).parents[2].resolve()
    MONTH = datetime.date.today().strftime('%Y%m')
    PROCESSED_PATH = BASE_PATH / 'data' / 'processed' / MONTH / 'AlivioCreditos'

    if not PROCESSED_PATH.exists():
        print(f"El directorio: {PROCESSED_PATH} no existe")
        print(f"Creando directorio: {PROCESSED_PATH}...")
        PROCESSED_PATH.mkdir(parents=True, exist_ok=True)

    try:
        with pd.ExcelWriter(f'{PROCESSED_PATH}/{MONTH}.xlsx', engine='openpyxl') as file:
            asignacion.to_excel(file, index=False)
        print(f'Archivo Creditos (processed) - {MONTH}.xlsx creado✅')
    except Exception as e:
        raise ErrorExportando(f'Error exportando processed Creditos: {e}') from e

    return asignacion

def aplicar_ranking_unico(asignacion:pd.DataFrame) -> dict[str,pd.DataFrame]:

    """
    Deja una sola oferta de ALIVIO_FINANCIERO por asociado, filtra a los
    créditos que efectivamente aplican y persiste la base de oferta en
    la capa Gold del proyecto.

    Pasos aplicados:
        - Deduplica por LLAVE (un crédito con codeudor podría aparecer
          bajo más de un ASO_IDENTIFICACION).
        - Dentro de cada ASO_IDENTIFICACION, rankea los créditos por
          (FACT_DIAS_DE_MORA * 1_000_000 + SALDO_TOTAL) descendente —
          la mora pesa mucho más que el saldo, que solo desempata.
        - Solo el crédito con ranking 1 conserva su ALIVIO_FINANCIERO;
          el resto se fuerza a 'No Aplica'.
        - Filtra a ALIVIO_FINANCIERO != 'No Aplica' y castea el valor
          restante (ya viene como '0.5', '0.35', etc. desde
          `calcular_alivio_financiero`) a PORCENTAJE_CONDONACION float.
        - Se queda con ASO_IDENTIFICACION, LLAVE (el pagaré del crédito
          que aplica) y PORCENTAJE_CONDONACION, y persiste esa base en
          data/output/YYYYMM/Creditos/base_oferta_creditos.xlsx.

    Parameters
    ----------
    asignacion : pd.DataFrame
        Resultado de `calcular_alivio_financiero`.

    Returns
    -------
    pd.DataFrame
        Base de oferta final: ASO_IDENTIFICACION, LLAVE,
        PORCENTAJE_CONDONACION — una fila por asociado, solo los que
        aplican a alivio.

    Raises
    ------
    ErrorExportando
        Si falla la creación del directorio o la escritura del archivo
        en data/output/.
    """
    asignacion = asignacion.drop_duplicates(subset='LLAVE', keep='first')

    score = asignacion['FACT_DIAS_DE_MORA'] * 1_000_000 + asignacion['SALDO_TOTAL']
    ranking = score.groupby(asignacion['ASO_IDENTIFICACION']).rank(method='first', ascending=False)

    asignacion = asignacion.assign(
        ALIVIO_FINANCIERO = np.where(ranking == 1, asignacion['ALIVIO_FINANCIERO'], 'No Aplica')
    )

    base_oferta = (
        asignacion
        .loc[lambda df: df['ALIVIO_FINANCIERO'] != 'No Aplica']
        .assign(
            PORCENTAJE_CONDONACION = lambda df:
                df['ALIVIO_FINANCIERO'].astype(float)
        )
        [['ASO_IDENTIFICACION', 
          'ASO_NOMBRE_COMPLETO', 
          'LLAVE', 
          'PORCENTAJE_CONDONACION']]
        
    )
    print(f'Asociados unicos a los que aplica alivio creditos: {len(base_oferta)}')
    
    # --- Persiste en Output (Gold) --- #

    BASE_PATH = Path(__file__).parents[2].resolve()
    MONTH = datetime.date.today().strftime('%Y%m')
    OUTPUT_PATH = BASE_PATH / 'data' / 'output' / MONTH / 'Creditos'

    if not OUTPUT_PATH.exists():
        print(f"El directorio: {OUTPUT_PATH} no existe")
        print(f"Creando directorio: {OUTPUT_PATH}...")
        OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    try:
        base_oferta.to_excel(
            OUTPUT_PATH / 'base_oferta_creditos.xlsx',
            index=False,
        )
        print(f'Base oferta Creditos (output) - {MONTH} exportada✅')
    except Exception as e:
        raise ErrorExportando(f'Error exportando output Creditos: {e}') from e

    return {'Creditos':base_oferta}
