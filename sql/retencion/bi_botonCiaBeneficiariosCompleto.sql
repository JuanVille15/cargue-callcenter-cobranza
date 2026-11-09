SELECT 
       [strIdentificacionAso]
      ,[strIdentificacionBen]
      ,[strDescBeneficiario]
      ,[strNombre]
      ,[strApellido1]
      ,[strApellido2]
      ,[strParentesco]
      ,[strProducto]
      ,[dtmFechaNacimientoBen]
      ,[numEdadBen] 
  FROM [BodegaCorporativa].[consulta].[botonCiaBeneficiariosCompleto] with (nolock)
  where
    [strProducto] = 'BENEFICIARIOS AUXILIO FUNERARIO'