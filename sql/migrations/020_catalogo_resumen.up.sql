-- 020: catálogo público y métricas. Aplicar tras 019 en copia respaldada.
-- No publica modelos automáticamente ni añade capacidades de hardware.
DELIMITER $$
CREATE PROCEDURE sp_catalogo_capacidades(IN p_modelo INT)
SQL SECURITY DEFINER
BEGIN
 SELECT c.nombre,c.descripcion,c.codigo FROM capacidades_modelo c
 JOIN modelos m ON m.id_modelo=c.id_modelo AND m.activo=1 AND m.publico=1
 WHERE c.id_modelo=p_modelo AND c.activo=1 ORDER BY c.codigo;
END$$
DROP PROCEDURE IF EXISTS sp_admin_resumen$$
CREATE PROCEDURE sp_admin_resumen()
SQL SECURITY DEFINER
BEGIN
 SELECT (SELECT COUNT(*) FROM modelos WHERE activo=1) AS modelos_activos,
 (SELECT COUNT(*) FROM vehiculos WHERE activo=1) AS unidades_activas,
 (SELECT COUNT(*) FROM usuarios WHERE rol='USUARIO' AND activo=1) AS clientes_activos,
 (SELECT COUNT(*) FROM asignaciones WHERE fin_utc IS NULL) AS unidades_asignadas,
 (SELECT COUNT(*) FROM vehiculos WHERE activo=1 AND estado_comercial='EXHIBICION') AS unidades_exhibicion,
 (SELECT COUNT(*) FROM demos WHERE activo=1 AND tipo='EMPRESA') AS demos_empresa_activas,
 (SELECT COUNT(*) FROM vehiculos v JOIN modelos m ON m.id_modelo=v.id_modelo AND m.activo=1 AND m.publico=1
 JOIN configuracion_invitados cfg ON cfg.id_vehiculo=v.id_vehiculo AND cfg.habilitada=1
 WHERE v.activo=1 AND v.estado_comercial='EXHIBICION'
 AND NOT EXISTS(SELECT 1 FROM asignaciones a WHERE a.id_vehiculo=v.id_vehiculo AND a.fin_utc IS NULL)
 AND NOT EXISTS(SELECT 1 FROM reservas_control r WHERE r.id_vehiculo=v.id_vehiculo)
 AND EXISTS(SELECT 1 FROM comandos_invitado ci JOIN comandos c ON c.id_comando=ci.id_comando
 WHERE ci.id_vehiculo=v.id_vehiculo AND c.id_vehiculo=v.id_vehiculo AND c.activo=1 AND c.nombre='DETENER')) AS unidades_prueba_libres;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('020_catalogo_resumen');
