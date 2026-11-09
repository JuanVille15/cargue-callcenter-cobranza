IF OBJECT_ID('tempdb.dbo.#Asociados') IS NOT NULL
	DROP TABLE #Asociados

IF OBJECT_ID('tempdb.dbo.#DetSolidaridad') IS NOT NULL
	DROP TABLE #DetSolidaridad

declare @Fecha date

SELECT @Fecha= MAX(dtmFechaInsercion) FROM BodegaCorporativa.bodega.factAsociatividad f WITH (NOLOCK)
WHERE BodegaCorporativa.$partition.PF_MES(f.dtmFechaInsercion) BETWEEN BodegaCorporativa.$partition.PF_MES(DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()) - 1, 0))
					AND BodegaCorporativa.$partition.pf_mes(GETDATE()) 
					AND strFuente = 'Cootaylor' AND IndRegistroActual = 1

select distinct 
				f.skTiempoTenencia,
				strIdentificacion, 
				nkcliente
				,strCodEstadoFuente as strCodEstadoAsociadoFuente,	
				strDescEstadoFuente strDescEstadoAsociadoFuente,	
				strCodEstadoHomologado strCodEstadoAsociadoHomologado,	
				strDescEstadoHomologado strDescEstadoAsociadoHomologado,
				skTiempoInicioVigencia,	
				skTiempoFinVigencia,
				dtmFechaInicio,
				dg.strDescRegional,
				f.dtmFechaInsercion
				Into #Asociados
				FROM BodegaCorporativa.bodega.factAsociatividad f with (nolock)
				INNER JOIN BodegaCorporativa.bodega.dimEstado ec on ec.skEstado = f.skEstadoCliente
				INNER JOIN BodegaCorporativa.bodega.dimgeografiagecc dg
							on f.skGeografiaGecc=dg.skGeografiaGecc
							and dg.indRegistroActual='1' and dg.strFuente='CooTaylor' and	dg.strAbreviaturaEmpresa='Coomeva'
				WHERE BodegaCorporativa.$partition.PF_MES(f.dtmFechaInsercion)= BodegaCorporativa.$partition.pf_mes(@Fecha)   
				AND f.indRegistroActual = 1
				AND f.nkProductoFuente = 'CooTaylor01ASO'
				AND (f.skEstadoCliente <> -1 or f.skEstadoCliente <> -2)
				AND ec.numCodTipoEstado = 1
				AND ec.strFuente = 'CooTaylor'
				AND  (ec.strCodEstadoFuente between 10 and 29 ) -- esto es para los activos


SELECT distinct
			asociado.skTiempoTenencia,
			--aso.strConsecutivoTransaccional,
			asociado.strIdentificacion,
			asociado.strDescEstadoAsociadoFuente,

			dp.strDescProductoFuente as strTipoPlan,
			ASO.strCodProductoFuente, 
			--dp.strDescProductoFuente,
			ASO.strCodTipoMovimiento ,
			CASE WHEN ASO.strCodTipoMovimiento ='C' THEN 'Inicio Plan'
					WHEN ASO.strCodTipoMovimiento ='I' THEN 'Incremento Plan'
					WHEN ASO.strCodTipoMovimiento ='D' THEN 'Disminucion Plan'
				END AS Transaccion,
			aso.numValorProteccionAcumuladaActual,
			aso.numValorCuotaAcumuladaActual,
			CAST(aso.dtmFechaInicio AS DATE) FechaAprobacion,
			CAst(aso.dtmFechaCreacion as DATE) FechaSolicitud,
			DATEDIFF(YEAR,C.dtmFechaNacimiento,ASO.dtmFechaCreacion) AS EdadTomo,
			aso.strCodEstadoProductoFuente, 
			est.strdescEstadofuente as strdescEstadoProductofuente, 
			CAST(aso.dtmFechaPerseverancia AS DATE) dtmFechaPerseverancia
			--asociado.dtmFechaInsercion,
			--GETDATE() dtmFechaActualizacion
			INTO #DetSolidaridad
			FROM  		#Asociados asociado
			INNER JOIN  bodegaCorporativa.bodega.dimCliente C with (nolock)
						ON 	asociado.strIdentificacion = C.strIdentificacion
						AND C.strFuente = 'CooTaylor'
			INNER JOIN	BodegaCorporativa.bodega.factAsociatividad aso with(nolock)
						ON asociado.strIdentificacion = aso.strIdentificacion
			INNER JOIN	BodegaCorporativa.bodega.dimDetalleProducto dp
						ON  aso.skDetalleProducto = dp.skDetalleProducto
						AND dp.strFuente ='Sipas'
			Inner join  BodegaCorporativa.bodega.dimEstado est
						ON aso.skEstadoProducto = est.skestado
						AND est.strfuente ='Sipas'
						and est.numCodTipoEstado = 2
			WHERE		BodegaCorporativa.$partition.pf_mes(ASO.dtmfechainsercion) = BodegaCorporativa.$partition.pf_mes(@Fecha)  
			AND			aso.strFuente = 'SIPAS' 
			AND			aso.IndRegistroActual = 1 
			AND			aso.strCodEstadoProductoFuente not in ( '6','9') --cancelados
			AND			ASO.strCodTipoMovimiento in ('C', 'I', 'D')
			AND dp.strCodComercial ='BAS'

SELECT * FROM #DetSolidaridad