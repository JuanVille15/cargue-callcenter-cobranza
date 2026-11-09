WITH FacSegmentos AS (
                         SELECT
                            strIdentificacion AS ID,
                            numEdad as Edad,
                            numCantidadAniosAntiguedad as Antiguedad,
			                numCantidadProductos as suma_productos
                         FROM BodegaCorporativa.bodega.factSegmentos
                         WHERE 
						 	BodegaCorporativa.$partition.pf_mes(dtmFechaInsercion) = BodegaCorporativa.$partition.pf_mes('?')
                    )
                    SELECT
                        dem.Documento as [strIdentificacion],
						dem.Tipo_Documento,
		                dem.Nombre_Tipo_Vinculacion as Tipo_Vinculacion,
		                dem.Estado_Civil,
		                dem.Personas_a_Cargo,
		                dem.Personas_a_Cargo_Menores_18,
		                dem.Sexo,
		                dem.Estrato,
		                dem.Nombre_Tipo_Vivienda,
		                dem.Nombre_Nivel_Academico,
		                dem.Ingresos,
		                dem.Egresos,
		                dem.Nombre_Ocupacion,
		                dem.Ptaje_acierta,
		                dem.Cuotas_canceladas_aportes,
						dem.Saldo_aportes as Saldoaportes,
		                dem.Segmento_Ciclo_de_Vida,
		                seg.Edad,
		                seg.Antiguedad,
		                seg.suma_productos
                    FROM BodegaCorporativa.Conocimiento.v_Demografica Dem
                    INNER JOIN FacSegmentos seg 
                        ON dem.Documento = seg.ID
                    WHERE 
						BodegaCorporativa.$partition.pf_mes(dem.dtmFechaInsercion) = BodegaCorporativa.$partition.pf_mes('?')