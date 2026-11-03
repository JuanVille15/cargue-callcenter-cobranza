# Alivio Financiero

Pipeline de datos que calcula y entrega automáticamente la oferta de alivio
financiero para tres poblaciones de asociados de Coomeva — **Moras
Tempranas**, **Inactivos** y **Créditos** — y la envía al centro de contacto
(Wolkvox) sin intervención manual.

Reemplaza un proceso previamente manual, disperso en scripts de R
independientes por cada población, sin trazabilidad de qué se calculó ni de
qué se entregó en cada corrida.

## Qué hace, de punta a punta

```
Extraer → Transformar → Decidir → Consolidar → Enviar
```

1. **Extrae** de Oracle (GCC), SQL Server (Bodega BI) y archivos compartidos
   de cartera (Excel).
2. **Transforma** cada población aplicando su lógica de negocio.
3. **Decide** quién recibe alivio — con un modelo de ML (Moras, Inactivos) o
   un motor de reglas (Créditos).
4. **Consolida** las tres ofertas en una sola base por asociado, resolviendo
   cruces entre procesos.
5. **Envía** el payload resultante al marcador Wolkvox vía API, y persiste
   la respuesta como evidencia.

Cada corrida completa se dispara con:

```bash
python main.py
```

## Arquitectura

El proyecto sigue una arquitectura de datos por capas ("medallion"): cada
corrida deja rastro físico en disco en tres momentos distintos, y el código
se organiza por responsabilidad — no hay un solo script gigante, sino cinco
capas que cada pipeline atraviesa en orden.

**Capas de datos**

| Capa | Carpeta | Contenido |
|---|---|---|
| Bronze | `data/raw/YYYYMM/` | Insumos crudos, tal cual se extrajeron de GCC, Bodega BI y archivos compartidos |
| Silver | `data/processed/YYYYMM/` | Datos ya transformados con la lógica de negocio, antes de decidir la oferta |
| Gold | `data/output/YYYYMM/` | Oferta final por proceso, consolidado, payload enviado y respuesta de Wolkvox |

**Capas de código**

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| Extracción | `src/extraccion/` | Trae los datos crudos (SQL contra GCC/Bodega BI, o archivos Excel) |
| Transformación | `src/transformacion/` | Aplica las reglas de negocio: limpieza, cruces, features, elegibilidad |
| Modelo | `src/Model/` | Feature engineering específico e inferencia de los modelos de ML |
| Pipelines | `src/pipelines/` | Orquesta cada proceso de punta a punta, en el orden correcto |
| Conexión | `src/conexion/` | Habla con los sistemas externos: Oracle (GCC), SQL Server (Bodega BI), Wolkvox |
| Utils | `src/utils/` | Configuración, excepciones de negocio, helpers compartidos entre módulos |

**Estructura completa del repositorio**

```
alivio/
├── main.py                        # Orquestador general — corre los 4 pipelines en orden
├── config/
│   └── config.yaml                # Rutas, queries, columnas requeridas, mapeo Wolkvox
├── sql/                           # Queries versionadas contra GCC
│   ├── validar_actualizacion_gcc.sql
│   ├── r10.sql
│   ├── facturaMT.sql
│   ├── Demografica.sql
│   ├── Perfil.sql
│   ├── vista_360.sql
│   └── Creditos.sql
├── Models/                        # Artefactos de ML serializados (.pkl)
│   ├── MT/
│   │   ├── Logi_Alivio.pkl        # Regresión logística — Moras Tempranas
│   │   └── Scaler_logit.pkl
│   └── Inactivos/
│       ├── randomforest_Inactivos.pkl
│       └── scaler_inactivos.pkl
├── data/
│   ├── raw/YYYYMM/                # Bronze
│   ├── processed/YYYYMM/          # Silver
│   └── output/YYYYMM/             # Gold
├── .env                           # Credenciales y config (no versionado)
└── src/
    ├── extraccion/
    │   ├── commons.py             # Insumos comunes a los 3 procesos (Demografica, Perfil, Vista360, R10)
    │   ├── Moras_tempranas.py     # Extracción específica de Moras
    │   ├── inactivos.py           # Extracción específica de Inactivos
    │   └── creditos.py            # Extracción específica de Créditos (SQL + archivos)
    ├── transformacion/
    │   ├── Moras_tempranas.py     # Reglas de negocio y cruces de Moras
    │   ├── Inactivos.py           # Reglas de negocio y cruces de Inactivos
    │   ├── Creditos.py            # Motor de reglas de Créditos (cálculo de ALIVIO_FINANCIERO)
    │   └── consolidado_final.py   # Consolidación de las 3 ofertas + payload Wolkvox
    ├── Model/
    │   ├── inferencia.py          # predict / build_output / export — compartido por Moras e Inactivos
    │   ├── Mt/build_df.py         # Feature engineering específico de Moras
    │   └── Inactivos/build_df.py  # Feature engineering específico de Inactivos
    ├── pipelines/
    │   ├── Moras.py               # Orquestador: extracción → transformación → modelo → oferta
    │   ├── Inactivos.py           # Orquestador: extracción → transformación → modelo → oferta
    │   ├── Creditos.py            # Orquestador: extracción → transformación → reglas → oferta
    │   └── Post.py                # Orquestador: consolidar → armar payload → enviar a Wolkvox
    ├── conexion/
    │   ├── gcc.py                 # Cliente Oracle (GCC) vía pyodbc
    │   ├── bodega.py              # Cliente SQL Server (Bodega BI) vía pyodbc
    │   └── wolkvox.py             # Cliente HTTP del marcador Wolkvox
    └── utils/
        ├── helpers.py             # load_config, extract_files, exportar, print_step, winsorizar
        ├── exepciones.py          # 13 excepciones de negocio
        └── validation.py          # val_gcc_actualizado — valida que el DW esté al día antes de correr
```

## Los 4 pipelines

`main.py` ejecuta, en orden, 4 pipelines independientes — cada uno con su
propia cadena extracción → transformación → decisión → persistencia:

| Pipeline | Extracción | Transformación | Decide | Persiste en |
|---|---|---|---|---|
| **Moras** (`pipelines/Moras.py`) | `extraccion/Moras_tempranas.py` | `transformacion/Moras_tempranas.py` + `Model/Mt/build_df.py` (features) | `Model/inferencia.py` — regresión logística | `data/output/YYYYMM/Mt/` |
| **Inactivos** (`pipelines/Inactivos.py`) | `extraccion/inactivos.py` | `transformacion/Inactivos.py` + `Model/Inactivos/build_df.py` (features) | `Model/inferencia.py` — Random Forest | `data/output/YYYYMM/Inactivos/` |
| **Créditos** (`pipelines/Creditos.py`) | `extraccion/creditos.py` | `transformacion/Creditos.py` (7 funciones: preparación, cruces, cálculo, priorización) | motor de reglas por tramos, en el propio módulo | `data/processed/.../AlivioCreditos/` y `data/output/YYYYMM/Creditos/` |
| **Post** (`pipelines/Post.py`) | — (consume la oferta de los 3 anteriores) | `transformacion/consolidado_final.py` — consolida y arma el payload | — (solo valida cruces y prioriza) | `data/output/YYYYMM/Consolidado/` + envío a Wolkvox |

Los primeros tres corren en paralelo conceptualmente (no dependen entre sí);
**Post** es el único que depende de que los tres anteriores hayan terminado,
porque consolida sus tres salidas en una sola oferta.

Un quinto módulo, `extraccion/commons.py`, corre antes que los 4 pipelines:
extrae los insumos que varios procesos comparten (vista demográfica, perfil
de vinculación, Vista 360, población R10) una sola vez, para que ningún
pipeline repita la misma consulta contra GCC o Bodega BI.

## Los tres procesos (Moras, Inactivos, Créditos)

| Proceso | Población | Cómo decide | Oferta |
|---|---|---|---|
| **Moras Tempranas** | Asociados con mora reciente | Regresión logística (umbral configurable, `threshold_mt`) | % variable |
| **Inactivos** | Asociados inactivos reactivables | Random Forest | 50% fijo |
| **Créditos** | Cartera de créditos cooperativos en mora | Motor de reglas por tramos de mora/antigüedad/producto | 35% – 50% |

La lógica de **Créditos** es una migración deliberada y acotada del script R
original: se trazaron sus dependencias reales antes de portarla, dejando
fuera explícitamente `TIPO_MODIFICACION` y `CONDONACION` (reglas de negocio
distintas, fuera del alcance de esta oferta).

## Consolidación y prioridad

Las tres ofertas se cruzan (`outer join`) por identificación del asociado.
Si alguien aplica a más de un proceso, se prioriza así:

1. **Inactivos**
2. **Créditos**
3. **Moras Tempranas**

Moras e Inactivos son poblaciones que nunca deberían cruzarse — si ocurre,
el proceso se detiene (`AliviosCruzadosError`) en vez de enviar una oferta
ambigua.

## Envío al centro de contacto (Wolkvox)

El consolidado se transforma en un payload JSON según el mapeo de campos
definido en `config.yaml` (`WOLKVOX.MAPEO_CAMPOS`) y se envía por POST.

- **Modo dry run**: `WOLKVOX_DRY_RUN=true` en `.env` arma el payload pero no
  lo envía — para probar el pipeline completo sin postear registros reales.
- **Evidencia persistida**: cada envío real deja `payload.json` (lo que se
  envió) y `response.json` (lo que confirmó Wolkvox) en
  `data/output/YYYYMM/Consolidado/`.

## Manejo de errores

Cada falla posible tiene su propio tipo de excepción (`src/utils/exepciones.py`),
capturada individualmente en `main.py` antes de un `except Exception`
genérico — conexión a GCC caída, DW desactualizado, población vacía,
artefacto de ML faltante, columnas requeridas ausentes, alivios cruzados,
fallo enviando a Wolkvox, entre otras. Ningún error se silencia ni se
reporta de forma genérica cuando puede identificarse la causa.

## Configuración

- **`config/config.yaml`**: rutas de insumos (`paths_mt`, `paths_inactivos`,
  `paths_creditos`, `common_paths`), queries SQL, columnas requeridas por
  proceso, artefactos de ML y configuración de Wolkvox.
- **`.env`**: credenciales de conexión (`GCC_CON`, `CON_BI`) y configuración
  de Wolkvox (`WOLKVOX_TOKEN`, `WOLKVOX_BASE_URL`, `WOLKVOX_CAMPAIGN_ID`,
  `WOLKVOX_DRY_RUN`). No se versiona.

## Estado actual

El pipeline corre de punta a punta (extracción → decisión → consolidación →
envío) con manejo de errores tipado y modo de prueba seguro.

Pendiente para operarlo sin supervisión constante:

- Pruebas automatizadas sobre la lógica de negocio (`transformacion/`).
- Logging persistente (hoy la traza de ejecución vive en `print()`, visible
  solo si alguien mira la consola en el momento).
- Control de versiones (Git) e integración continua.

## Requisitos

- Python 3.13 (`.venv313`)
- Driver Oracle Instant Client 21.3
- ODBC Driver 17 for SQL Server
- Acceso de red a los recursos compartidos listados en `config.yaml`