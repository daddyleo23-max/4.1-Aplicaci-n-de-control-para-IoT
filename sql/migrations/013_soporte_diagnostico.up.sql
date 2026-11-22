-- Consentimiento temporal de diagnóstico, sin permiso de movimiento.
-- Aplicar sólo sobre la copia validada después de 012. DDL hace commit implícito.
CREATE TABLE permisos_soporte (
 id_permiso BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 id_asignacion BIGINT NOT NULL,
 id_administrador BIGINT NOT NULL,
 creado_utc DATETIME(6) NOT NULL,
 expira_utc DATETIME(6) NOT NULL,
 revocado_utc DATETIME(6) NULL,
 INDEX idx_soporte_acceso(id_administrador,id_asignacion,expira_utc),
 FOREIGN KEY(id_asignacion) REFERENCES asignaciones(id_asignacion) ON DELETE RESTRICT,
 FOREIGN KEY(id_administrador) REFERENCES usuarios(id_usuario) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
DELIMITER $$
CREATE PROCEDURE sp_soporte_conceder(IN p_actor BIGINT, IN p_unidad INT, IN p_admin BIGINT, IN p_minutos INT)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_asignacion BIGINT DEFAULT NULL;
 DECLARE v_unidad INT DEFAULT NULL;
 SELECT id_vehiculo INTO v_unidad FROM vehiculos WHERE id_vehiculo=p_unidad AND activo=1 FOR UPDATE;
 SELECT id_asignacion INTO v_asignacion FROM asignaciones
 WHERE id_vehiculo=v_unidad AND id_usuario=p_actor AND fin_utc IS NULL FOR UPDATE;
 IF v_asignacion IS NULL OR p_minutos NOT BETWEEN 1 AND 30 OR NOT EXISTS(
 SELECT 1 FROM usuarios WHERE id_usuario=p_admin AND rol='ADMINISTRADOR' AND activo=1
 ) OR NOT EXISTS(SELECT 1 FROM usuarios WHERE id_usuario=p_actor AND activo=1 AND rol='USUARIO') THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Consentimiento o destinatario incompatible';
 END IF;
 UPDATE permisos_soporte SET revocado_utc=UTC_TIMESTAMP(6)
 WHERE id_asignacion=v_asignacion AND id_administrador=p_admin AND revocado_utc IS NULL;
 INSERT INTO permisos_soporte(id_asignacion,id_administrador,creado_utc,expira_utc)
 VALUES(v_asignacion,p_admin,UTC_TIMESTAMP(6),TIMESTAMPADD(MINUTE,p_minutos,UTC_TIMESTAMP(6)));
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
 VALUES(p_actor,'CONCEDER_SOPORTE','vehiculo',CAST(p_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
 SELECT id_permiso,expira_utc FROM permisos_soporte WHERE id_permiso=(
 SELECT MAX(id_permiso) FROM permisos_soporte WHERE id_asignacion=v_asignacion AND id_administrador=p_admin);
END$$
CREATE PROCEDURE sp_soporte_acceso(IN p_admin BIGINT, IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
 SELECT p.id_permiso FROM permisos_soporte p
 JOIN asignaciones a ON a.id_asignacion=p.id_asignacion AND a.fin_utc IS NULL
 JOIN vehiculos v ON v.id_vehiculo=a.id_vehiculo AND v.activo=1
 JOIN usuarios u ON u.id_usuario=a.id_usuario AND u.activo=1 AND u.rol='USUARIO'
 JOIN usuarios ad ON ad.id_usuario=p.id_administrador AND ad.activo=1 AND ad.rol='ADMINISTRADOR'
 WHERE p.id_administrador=p_admin AND a.id_vehiculo=p_unidad
 AND p.revocado_utc IS NULL AND p.expira_utc>UTC_TIMESTAMP(6) LIMIT 1;
END$$
CREATE PROCEDURE sp_soporte_listar(IN p_actor BIGINT, IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
 SELECT p.id_permiso,p.id_administrador,ad.nombre AS administrador,p.creado_utc,p.expira_utc,p.revocado_utc,
 (p.revocado_utc IS NULL AND p.expira_utc>UTC_TIMESTAMP(6) AND a.fin_utc IS NULL) AS vigente
 FROM permisos_soporte p JOIN asignaciones a ON a.id_asignacion=p.id_asignacion
 JOIN usuarios ad ON ad.id_usuario=p.id_administrador
 WHERE a.id_vehiculo=p_unidad AND (a.id_usuario=p_actor OR p.id_administrador=p_actor)
 ORDER BY p.id_permiso DESC LIMIT 100;
END$$
CREATE PROCEDURE sp_soporte_revocar(IN p_actor BIGINT, IN p_unidad INT, IN p_permiso BIGINT)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_id BIGINT DEFAULT NULL;
 SELECT p.id_permiso INTO v_id FROM permisos_soporte p JOIN asignaciones a ON a.id_asignacion=p.id_asignacion
 WHERE p.id_permiso=p_permiso AND a.id_vehiculo=p_unidad AND a.id_usuario=p_actor AND a.fin_utc IS NULL FOR UPDATE;
 IF v_id IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Permiso ajeno o inexistente'; END IF;
 UPDATE permisos_soporte SET revocado_utc=COALESCE(revocado_utc,UTC_TIMESTAMP(6)) WHERE id_permiso=v_id;
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
 VALUES(p_actor,'REVOCAR_SOPORTE','vehiculo',CAST(p_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('013_soporte_diagnostico');
