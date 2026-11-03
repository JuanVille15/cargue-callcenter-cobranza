SELECT
      dtmFechaInsercion
	  ,[strIdentificacion]
      ,[strPerfil]
      ,[strAgrupacionPerfil]
  FROM [BodegaCorporativa].[bodega].[V_SegmentosPerfilEstrategico]
  WHERE BodegaCorporativa.$partition.pf_mes(dtmFechaInsercion) = BodegaCorporativa.$partition.pf_mes(?)