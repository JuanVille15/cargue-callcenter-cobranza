WITH FacSegmentos AS (
                         SELECT
                            strPeriodo AS Periodo,
                            strIdentificacion AS ID,
                            numEdad as Edad,
                            numCantidadAniosAntiguedad as Antiguedad,
			                numCantidadProductos as suma_productos
                         FROM BodegaCorporativa.bodega.factSegmentos
                         WHERE BodegaCorporativa.$partition.pf_mes(dtmFechaInsercion) = BodegaCorporativa.$partition.pf_mes(?)
                    )
                    SELECT
                        dem.Documento as [Identificacion],
                        dem.Estrato as [estrato],
                        dem.Ingresos as [ingresos],
                        dem.Saldo_aportes as [saldo_aportes],
                        seg.Antiguedad as [antiguedad_anios],
                        seg.suma_productos
                    FROM BodegaCorporativa.Conocimiento.v_Demografica Dem
                    INNER JOIN FacSegmentos seg
                        ON dem.strPeriodo = seg.Periodo 
                        AND dem.Documento = seg.ID
                    WHERE BodegaCorporativa.$partition.pf_mes(dem.dtmFechaInsercion) = BodegaCorporativa.$partition.pf_mes(?)