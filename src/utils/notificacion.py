import traceback
import requests
import datetime
import os
import json
import win32com.client as win32
from pathlib import Path
from src.utils.exepciones import ErrorNotificacion

def _destinatarios() -> list[str]:
    return [d.strip() for d in os.environ.get('EMAIL_TO', '').split(',') if d.strip()]

def _body(response:requests.Response) -> str:
    
    # --- Se extrae el cuerpo de la respuesta --- #
    
    try:
        body = response.json()
    except ValueError:
        body = {
            'code':response.status_code, 
            'msg': response.text[:500], 
            'error': 'Respuesta de Wolkvox no es un JSON Valido'
        }
    # --- Se extrae payload --- #
    
    BASE_PATH = Path(__file__).parents[2].resolve()
    PAYLOAD_PATH = BASE_PATH / 'data' / 'output' / datetime.date.today().strftime('%Y%m') / 'Consolidado'
    
    if not Path(PAYLOAD_PATH).exists():
        raise FileNotFoundError(f'El directorio: {PAYLOAD_PATH} no existe...')
    
    PAYLOAD = PAYLOAD_PATH / 'payload.json'
    
    if not PAYLOAD.exists():
        raise FileNotFoundError(f'No se encontro payload en: {PAYLOAD_PATH}...')
    
    try:
        with open(PAYLOAD, mode='r', encoding='utf-8') as f:
            payload = json.load(f)
    except Exception as e:
        print(f'Ocurrio un error leyendo: {PAYLOAD.stem} - {e}')
        raise e

    valores = {
    'Moras': sum([int(r.get('opt1','')) for r in payload]), 
    'Inactivos': sum([int(r.get('opt2','')) for r in payload]),
    'Creditos': sum([int(r.get('opt3','')) for r in payload]),
    }
    
    if int(body['code']) == 201:
        
        cuerpo = f'''
        <html>
        <body style="font-family: Segoe UI, Arial, sans-serif; color: #333;">
        <h1>Notificacion Automatica Pipeline Alivio: {datetime.datetime.today().strftime('%d-%m-%Y')}</h1>
        <p> Peticion realizada con respuesta: {int(body['code'])}</p>
        <p> Api message: {body['msg']}</p>
        <p> Api Error: {'None' if not body['error'] else body['error']}</p>
        <h2>Detalle Peticion - Total Registros: {sum(valores.values()):,} </h2>
        <br>
        <table style="border-collapse: collapse;" cellpadding="0" cellspacing="0">
        <tr style="background-color: #006400; color: white;">
            <th style="border: 1px solid #ccc; padding: 6px 14px; text-align: left; background-color: #f4f4f4;">Actor Gestion</th>
            <th style="border: 1px solid #ccc; padding: 6px 14px; text-align: left; background-color: #f4f4f4;">Total oferta</th>
        </tr>

        <tr>
            <td style="border: 1px solid #ccc; padding: 6px 14px;">Moras</td>
            <td style="border: 1px solid #ccc; padding: 6px 14px;">{valores['Moras']:,}</td>
        </tr>

        <tr>
            <td style="border: 1px solid #ccc; padding: 6px 14px;">Inactivos</td>
            <td style="border: 1px solid #ccc; padding: 6px 14px;">{valores['Inactivos']:,}</td>
        </tr>

        <tr>
            <td style="border: 1px solid #ccc; padding: 6px 14px;">Creditos</td>
            <td style="border: 1px solid #ccc; padding: 6px 14px;">{valores['Creditos']:,}</td>
        </tr>
        </table>
        </body>
        </html>
        '''
    else:
        cuerpo = f'''
        <html>
        <body style="font-family: Segoe UI, Arial, sans-serif; color: #333;">
        <h1>Notificacion Automatica Pipeline Alivio: {datetime.datetime.today().strftime('%d-%m-%Y')}</h1>
        <p> Peticion con error: {int(body['code'])}</p>
        <p> Api message: {body['msg']}</p>
        <p> Api Error: {'None' if not body['error'] else body['error']}</p>
        </body>
        </html>
        '''
        
    return cuerpo
    
def enviar_notificacion(response:requests.Response) -> None:
    
    # --- Generamos los destinatarios --- #
    
    destinatarios = _destinatarios()
    if not destinatarios:
        print('No hay destinatarios configurados en (EMAIL_TO): Se omite Notificacion')
        return None
    
    asunto = f'Resumen Carga Asociados - API WOLKVOX: {datetime.datetime.today()}'
    
    try:
        cuerpo = _body(response=response)
    except Exception as e:
        print(f'No se pudo construir el cuerpo de la notificacion: {e}')
        traceback.print_exc()
        raise ErrorNotificacion(f'Fallo construyendo el cuerpo de la notificacion: {e}') from e

    try:
        outlook = win32.Dispatch('Outlook.Application')
        mail = outlook.CreateItem(0)
        mail.To = ';'.join(destinatarios)
        mail.Subject = asunto
        mail.HTMLBody = cuerpo
        mail.Send()
    except Exception as e:
        print(f'No se puede enviar la notificacion por correo: {e}')
        traceback.print_exc()
        raise ErrorNotificacion(f'Fallo el envio de la notificacion: {e}') from e