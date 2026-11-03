import json
import datetime
import requests
from pathlib import Path
from dotenv import dotenv_values
from src.utils.exepciones import ErrorEnvioOferta, ErrorExportando

def _persistir_respuesta(peticion: requests.Response) -> None:

    """
    Persiste la respuesta de Wolkvox como JSON en la capa Output, como
    evidencia de lo que confirmó el envío.

    Parameters
    ----------
    peticion : requests.Response
        Respuesta de `enviar_oferta`, exitosa o con status de error.

    Raises
    ------
    ErrorExportando
        Si falla la creación del directorio o la escritura del JSON.
    """

    BASE_PATH = Path(__file__).parents[2].resolve()
    MONTH = datetime.date.today().strftime('%Y%m')
    OUTPUT_PATH = BASE_PATH / 'data' / 'output' / MONTH / 'Consolidado'

    if not OUTPUT_PATH.exists():
        OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    try:
        cuerpo = peticion.json()
    except ValueError:
        cuerpo = peticion.text

    try:
        with open(OUTPUT_PATH / 'response.json', 'w', encoding='utf-8') as f:
            json.dump(cuerpo, f, ensure_ascii=False, indent=2)
        print(f'Respuesta Wolkvox (output) - {MONTH} exportada✅')
    except Exception as e:
        raise ErrorExportando(f'Error exportando respuesta Wolkvox: {e}') from e

def _headers(env) -> dict:

    """
    Arma los headers de autenticación requeridos por la API de Wolkvox.

    Parameters
    ----------
    env : dict
        Variables de entorno cargadas (`dotenv_values()`), debe incluir
        'WOLKVOX_CONTENT_TYPE' y 'WOLKVOX_TOKEN'.

    Returns
    -------
    dict
        Headers listos para pasar a `requests.post(headers=...)`.
    """

    HEADERS = {
        'Content-Type': env['WOLKVOX_CONTENT_TYPE'],
        'wolkvox-token': env['WOLKVOX_TOKEN']
    }

    return HEADERS

def enviar_oferta(payload: list[dict]) -> requests.Response:

    """
    Envía el payload consolidado de ofertas a Wolkvox vía POST.

    Arma la URL y los headers a partir de las variables de entorno
    (.env: WOLKVOX_BASE_URL, WOLKVOX_CAMPAIGN_ID, WOLKVOX_TOKEN,
    WOLKVOX_CONTENT_TYPE), realiza el POST con `json=payload` y valida
    la respuesta con `raise_for_status()`. Cualquier falla de red,
    timeout o status HTTP de error (4xx/5xx) se traduce a
    `ErrorEnvioOferta`.

    Parameters
    ----------
    payload : list[dict]
        Lista de registros a enviar, resultado de `build_payload`.

    Returns
    -------
    requests.Response
        Respuesta exitosa de Wolkvox (status 2xx).

    Raises
    ------
    ErrorEnvioOferta
        Si falla la conexión, se agota el timeout, o Wolkvox responde
        con un status de error.
    """

    env = dotenv_values()
    
    HEADERS = _headers(env=env)
    URL = f'{env['WOLKVOX_BASE_URL']}?api=add_record&type_campaign=preview&campaign_id={env['WOLKVOX_CAMPAIGN_ID']}'
    
    # --- Se realiza el POST y se manejan errores --- #
    
    try:
        ## --- POST mediante  libreria request --- ##
        peticion = requests.post(
            url=URL, 
            json=payload, 
            headers=HEADERS, 
            timeout=60, 
        )
        
        peticion.raise_for_status()

    except requests.exceptions.ConnectionError as e:
        raise ErrorEnvioOferta(f'No se pudo conectar con Wolkvox: {e}') from e
    except requests.exceptions.Timeout as e:
        raise ErrorEnvioOferta(f'Tiempo de espera agotado al conectar con Wolkvox: {e}') from e
    except requests.exceptions.HTTPError as e:
        error = ErrorEnvioOferta(f'Wolkvox respondio con error: {peticion.status_code}: {e}')
        error.response = peticion #type:ignore
        try:
            _persistir_respuesta(peticion=peticion)
        except ErrorExportando as exp:
            print(f'No se pudo persistir la respuesta de error en disco: {exp}')      
        raise error from e
    except requests.exceptions.RequestException as e:
        raise ErrorEnvioOferta(f'Error inesperado enviando la oferta a Wolkvox: {e}') from e

    print(f'Oferta enviada a Wolkvox✅ — status {peticion.status_code}')
    
    try:
        _persistir_respuesta(peticion=peticion)
    except ErrorExportando as exp:
        print(f'No se pudo persistir la respuesta en disco: {exp}')

    return peticion
