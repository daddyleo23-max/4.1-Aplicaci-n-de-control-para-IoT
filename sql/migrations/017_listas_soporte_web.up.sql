-- Listas mínimas para la interfaz de consentimiento; aplicar tras 016.
DELIMITER $$
CREATE PROCEDURE sp_soporte_destinatarios()
SQL SECURITY DEFINER
BEGIN
 SELECT id_usuario AS id_administrador,nombre FROM usuarios
 WHERE rol='ADMINISTRADOR' AND activo=1 ORDER BY nombre,id_usuario;
END$$
CREATE PROCEDURE sp_soporte_mis_permisos(IN p_admin BIGINT)
SQL SECURITY DEFINER
BEGIN
 SELECT p.id_permiso,p.operativo,p.expira_utc,v.id_vehiculo,v.nombre,
 v.identificador_unidad,m.nombre AS nombre_modelo
 FROM permisos_soporte p JOIN usuarios ad ON ad.id_usuario=p.id_administrador AND ad.activo=1 AND ad.rol='ADMINISTRADOR'
 JOIN asignaciones a ON a.id_asignacion=p.id_asignacion AND a.fin_utc IS NULL
 JOIN usuarios comprador ON comprador.id_usuario=a.id_usuario AND comprador.activo=1 AND comprador.rol='USUARIO'
 JOIN vehiculos v ON v.id_vehiculo=a.id_vehiculo AND v.activo=1
 LEFT JOIN modelos m ON m.id_modelo=v.id_modelo
 WHERE p.id_administrador=p_admin AND p.revocado_utc IS NULL AND p.expira_utc>UTC_TIMESTAMP(6)
 ORDER BY p.expira_utc DESC,p.id_permiso DESC LIMIT 100;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('017_listas_soporte_web');
