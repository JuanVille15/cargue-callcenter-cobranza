SELECT
            ? AS Fecha,
            f.Identificacion,
            f.Edad,
            f.Segmento,
            f.[ValorPerseverancia],
            f.[Tipo Vinculacion],
            f.ReservaMatematica,
            f.Rango_Score,
            f.Estrato, 
            f.SaldoAportes, 
            f.numValorIngresos, 
            f.Antiguedad,
			f.[Antiguedad Actual (Años)],
            f.numCantidadProductos,
            f.[Puntaje Acierta]
        FROM [Operaciones].[dbo].[ConsultaIntegral360] f WITH (NOLOCK)
        WHERE $partition.pf_mes(f.dtmFechaInsercion) = $partition.pf_mes(?);