import sys
import traceback
import warnings
from dotenv import dotenv_values
from src.utils.helpers import print_step, load_config
from src.utils.exepciones import (
    GCCconexionError, GCCdesactualizadoError,
    ErrorConsultadoDemografica, ErrorConsultadoPerfil,
    EmptyDataFrameError, ErrorCargandoArterfacto, ErrorExportando,
    ExportacionAlivioInacError, ErrorConsultadoVista360,
    ColNecesariasError, AliviosCruzadosError, ErrorEnvioOferta, 
    ErrorNotificacion
)
from src.utils.notificacion import enviar_notificacion
from src.utils.validation import val_gcc_actualizado
from src.extraccion.commons import extract_commons
from src.pipelines import Moras, Inactivos, Creditos, Post

warnings.filterwarnings('ignore')

def main():
    cfg = load_config()
    env = dotenv_values()
    dry_run = str(env.get('WOLKVOX_DRY_RUN', 'false')).strip().lower() == 'true'

    try:
        print_step('[1/7] Validando actualización DW GCC')
        val_gcc_actualizado(cfg['queries']['validacion_actualizacion'])

        print_step('[2/7] Extrayendo bases comunes')
        common_files = extract_commons(
            demo_path=cfg['queries']['demografica'],
            perfil_path=cfg['queries']['perfiles'],
            r10_sql_path=cfg['queries']['r10'],
            vista_path=cfg['queries']['vista360'],
            common_paths=cfg['common_paths'],
        )

        # --- Se guardan los Outputs --- #
        
        outputs = {}
        
        print_step('[3/7] Pipeline Moras Tempranas')
        outputs.update(Moras.run_moras(cfg=cfg, common_files=common_files))
        print_step(f'PROCESO COMPLETADO ✅ — Oferta MT: {len(outputs['Moras'])} asociados')
        
        print_step('[4/7] Pipeline Inactivos')
        outputs.update(Inactivos.run_inactivos(cfg=cfg, common_files=common_files))
        print_step(f'PROCESO COMPLETADO ✅ — Oferta INACTIVOS: {len(outputs['Inactivos'])} asociados')
        
        print_step('[5/7] Pipeline Creditos')
        outputs.update(Creditos.run_creditos(cfg=cfg, common_files=common_files))
        print_step(f'PROCESO COMPLETADO ✅ — Oferta CREDITOS: {len(outputs['Creditos'])} asociados')
        
        print_step('[6/7] Consolidando, armando payload y enviando a Wolkvox')
        respuesta = Post.run_post(outputs=outputs, cfg=cfg, dry_run=dry_run)
        if respuesta is None:
            print_step('PROCESO COMPLETADO ✅ — Payload generado (dry run), no se envió')
        else:
            print_step(f'PROCESO COMPLETADO ✅ — Oferta enviada a Wolkvox: status {respuesta.status_code}')
            
        print_step('[7/7] Enviando Notificacion Insercion...')
        if respuesta is None:
            print_step('PROCESO COMPLETADO ✅ — Pipeline ejecutado en dry run, no se envió notificacion')
        else:
            try:
                enviar_notificacion(response=respuesta, env=env)
                print_step('PROCESO COMPLETADO - Notificacion Enviada Exitosamente ✅')
            except ErrorNotificacion as e:
                print(f'Pipeline completado, pero no se pudo enviar la notificación: {e}')
                traceback.print_exc()
                sys.exit(2)

        
    except GCCconexionError as e:
        print(f'Error de conexión GCC: {e}')
        traceback.print_exc()
        sys.exit(1)
    except GCCdesactualizadoError as e:
        print(f'DW GCC desactualizado: {e}')
        traceback.print_exc()
        sys.exit(1)
    except (ErrorConsultadoDemografica, ErrorConsultadoPerfil, ErrorConsultadoVista360) as e:
        print(f'Error extrayendo bases comunes: {e}')
        traceback.print_exc()
        sys.exit(1)
    except EmptyDataFrameError as e:
        print(f'Población vacía — el proceso se detiene: {e}')
        traceback.print_exc()
        sys.exit(1)
    except ErrorCargandoArterfacto as e:
        print(f'Error cargando artefacto ML: {e}')
        traceback.print_exc()
        sys.exit(1)
    except ErrorExportando as e:
        print(f'Error exportando resultados: {e}')
        traceback.print_exc()
        sys.exit(1)
    except ExportacionAlivioInacError as e:
        print(f'Error exportando oferta alivio: {e}')
        traceback.print_exc()
        sys.exit(1)
    except ColNecesariasError as e:
        print(f'Error consolidando ofertas — columnas faltantes: {e}')
        traceback.print_exc()
        sys.exit(1)
    except AliviosCruzadosError as e:
        print(f'Error consolidando ofertas — alivios cruzados: {e}')
        traceback.print_exc()
        sys.exit(1)
    except ErrorEnvioOferta as e:
        print(f'Error enviando oferta a Wolkvox: {e}')
        traceback.print_exc()
        respuesta_error = getattr(e, 'response', None)
        if respuesta_error:
            try:
                enviar_notificacion(response=respuesta_error, env=env)
            except Exception as notif_error:
                print(f'Adicionalmente, no se pudo notificar por correo: {notif_error}')
        sys.exit(1)
    except Exception as e:
        print(f'Error inesperado: {e}')
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()