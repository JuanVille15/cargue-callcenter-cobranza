import pandas as pd
import requests
from src.transformacion.consolidado_final import (
    consolidar_ofertas, build_payload,
)
from src.conexion.wolkvox import enviar_oferta

def run_post(
    outputs:dict[str,pd.DataFrame],
    cfg: dict,
    dry_run: bool = False,
) -> requests.Response | None:

    """
    Orquesta el cierre del proceso: consolida las ofertas de los 3
    procesos, arma el payload y lo envía a Wolkvox.

    Parameters
    ----------
    outputs : dict[str, pd.DataFrame]
        Ofertas finales de cada proceso ('Moras', 'Inactivos',
        'Creditos'), resultado de unir los diccionarios de
        `run_moras`, `run_inactivos` y `run_creditos`.
    cfg : dict
        Configuración del proyecto (config.yaml), debe incluir
        `columnas.col_necesarias_post` y `WOLKVOX`.
    dry_run : bool, default False
        Si es True, arma el payload pero NO lo envía a Wolkvox — útil
        para probar el pipeline sin postear registros reales.
        Controlado desde `.env` (WOLKVOX_DRY_RUN).

    Returns
    -------
    requests.Response | None
        Respuesta de Wolkvox si se envió (`dry_run=False`), o `None`
        si fue una corrida en dry run.
    """

    print('  → Consolidando Ofertas Finales...')
    consolidado= consolidar_ofertas(
        outputs=outputs,
        cols=cfg['columnas']['col_necesarias_post']
    )
    print('  → Creando Cuerpo de peticion...')
    payload = build_payload(
        consolidado=consolidado,
        payload_config=cfg['WOLKVOX']
    )

    if dry_run:
        print(f'  → DRY RUN activo: no se envía la oferta a Wolkvox ({len(payload)} registros)')
        return None

    print(f'  → Enviando oferta a Wolkvox... ({len(payload)} registros)')
    respuesta = enviar_oferta(payload=payload)

    return respuesta