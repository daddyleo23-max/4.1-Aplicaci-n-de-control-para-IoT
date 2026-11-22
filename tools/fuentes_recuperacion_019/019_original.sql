-- 019: exclusividad de empresa. Requiere 001–018 y respaldo verificado.
-- Cerrar TODAS las reservas y detener backend antes de aplicar en copia.
-- DDL con commits implícitos; no repetir si queda parcial.
DELIMITER $$
CREATE PROCEDURE sp_preflight_019()
BEGIN
 IF EXISTS(SELECT 1 FROM reservas_control) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Cierra todas las reservas antes de migrar'; END IF;
END$$
CALL sp_preflight_019()$$
DROP PROCEDURE sp_preflight_019$$
DELIMITER ;
ALTER TABLE sesiones_control MODIFY id_asignacion BIGINT NULL,
 ADD COLUMN id_vehiculo INT NULL,
 ADD CONSTRAINT fk_control_unidad FOREIGN KEY(id_vehiculo) REFERENCES vehiculos(id_vehiculo) ON DELETE RESTRICT;
UPDATE sesiones_control c JOIN asignaciones a ON a.id_asignacion=c.id_asignacion SET c.id_vehiculo=a.id_vehiculo;
ALTER TABLE sesiones_control MODIFY id_vehiculo INT NOT NULL;
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_control_adquirir$$
CREATE PROCEDURE sp_control_adquirir(IN p_sesion BIGINT, IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_lock INT DEFAULT NULL;
 DECLARE v_asignacion BIGINT DEFAULT NULL;
 DECLARE v_actor BIGINT DEFAULT NULL;
 DECLARE v_expira DATETIME(6);
 DECLARE v_control BIGINT;
 DECLARE v_permiso BIGINT DEFAULT NULL;
 SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=p_unidad AND activo=1 FOR UPDATE;
 SELECT a.id_asignacion,s.id_usuario,
 LEAST(s.expira_utc,TIMESTAMPADD(SECOND,45,UTC_TIMESTAMP(6)),
       IF(u.rol='ADMINISTRADOR',p.expira_utc,s.expira_utc)),
 IF(u.rol='ADMINISTRADOR',p.id_permiso,NULL)
 INTO v_asignacion,v_actor,v_expira,v_permiso
 FROM sesiones s JOIN usuarios u ON u.id_usuario=s.id_usuario AND u.activo=1
 JOIN asignaciones a ON a.id_vehiculo=v_lock AND a.fin_utc IS NULL
 LEFT JOIN usuarios propietario ON propietario.id_usuario=a.id_usuario
 LEFT JOIN permisos_soporte p ON p.id_asignacion=a.id_asignacion AND p.id_administrador=u.id_usuario
 AND p.operativo=1 AND p.revocado_utc IS NULL AND p.expira_utc>UTC_TIMESTAMP(6)
 WHERE s.id_sesion=p_sesion AND s.revocada_utc IS NULL AND s.expira_utc>UTC_TIMESTAMP(6)
 AND ((u.rol='USUARIO' AND a.id_usuario=u.id_usuario) OR (u.rol='ADMINISTRADOR' AND p.id_permiso IS NOT NULL))
 ORDER BY p.id_permiso DESC LIMIT 1;
 IF v_asignacion IS NULL AND v_lock IS NOT NULL AND NOT EXISTS(
 SELECT 1 FROM asignaciones WHERE id_vehiculo=v_lock AND fin_utc IS NULL) THEN
 SELECT s.id_usuario,LEAST(s.expira_utc,TIMESTAMPADD(SECOND,45,UTC_TIMESTAMP(6))) INTO v_actor,v_expira
 FROM sesiones s JOIN usuarios u ON u.id_usuario=s.id_usuario AND u.activo=1 AND u.rol='ADMINISTRADOR'
 WHERE s.id_sesion=p_sesion AND s.revocada_utc IS NULL AND s.expira_utc>UTC_TIMESTAMP(6);
 END IF;
 IF v_actor IS NULL OR NOT EXISTS(SELECT 1 FROM comandos WHERE id_vehiculo=p_unidad AND nombre='DETENER' AND activo=1) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Sesion, propiedad o DETENER incompatibles'; END IF;
 IF EXISTS(SELECT 1 FROM reservas_control WHERE id_vehiculo=p_unidad) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La unidad conserva otra reserva o detencion pendiente'; END IF;
 INSERT INTO sesiones_control(id_sesion,id_asignacion,id_permiso,id_vehiculo,inicio_utc,expira_utc)
 VALUES(p_sesion,v_asignacion,v_permiso,p_unidad,UTC_TIMESTAMP(6),v_expira);
 SET v_control=LAST_INSERT_ID();
 INSERT INTO reservas_control(id_vehiculo,id_control,creada_utc) VALUES(p_unidad,v_control,UTC_TIMESTAMP(6));
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
 VALUES(v_actor,IF(v_asignacion IS NULL,'RESERVAR_EMPRESA',IF(v_permiso IS NULL,'RESERVAR_COMPRADOR','RESERVAR_SOPORTE')),'vehiculo',CAST(p_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),JSON_OBJECT('id_control',v_control));
 SELECT v_control AS id_control,p_unidad AS id_vehiculo,v_expira AS expira_utc;
END$$
DROP PROCEDURE IF EXISTS sp_control_exigir$$
CREATE PROCEDURE sp_control_exigir(IN p_control BIGINT, IN p_sesion BIGINT, IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_lock INT;
 SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=p_unidad FOR UPDATE;
 IF NOT EXISTS(
 SELECT 1 FROM reservas_control r JOIN sesiones_control c ON c.id_control=r.id_control
 JOIN sesiones s ON s.id_sesion=c.id_sesion AND s.revocada_utc IS NULL AND s.expira_utc>UTC_TIMESTAMP(6)
 JOIN usuarios u ON u.id_usuario=s.id_usuario AND u.activo=1
 LEFT JOIN asignaciones a ON a.id_asignacion=c.id_asignacion AND a.fin_utc IS NULL
 LEFT JOIN usuarios propietario ON propietario.id_usuario=a.id_usuario
 LEFT JOIN permisos_soporte p ON p.id_permiso=c.id_permiso AND p.id_asignacion=a.id_asignacion
 JOIN vehiculos v ON v.id_vehiculo=c.id_vehiculo AND v.activo=1
 WHERE c.id_vehiculo=r.id_vehiculo AND r.id_vehiculo=p_unidad AND c.id_control=p_control AND c.id_sesion=p_sesion AND r.estado='ACTIVA'
 AND c.fin_utc IS NULL AND c.expira_utc>UTC_TIMESTAMP(6)
 AND ((c.id_asignacion IS NULL AND c.id_permiso IS NULL AND u.rol='ADMINISTRADOR'
 AND NOT EXISTS(SELECT 1 FROM asignaciones actual WHERE actual.id_vehiculo=p_unidad AND actual.fin_utc IS NULL))
 OR (a.id_asignacion IS NOT NULL AND a.fin_utc IS NULL AND propietario.activo=1 AND propietario.rol='USUARIO'
 AND ((u.rol='USUARIO' AND a.id_usuario=u.id_usuario AND c.id_permiso IS NULL)
 OR (u.rol='ADMINISTRADOR' AND p.id_administrador=u.id_usuario AND p.operativo=1
 AND p.revocado_utc IS NULL AND p.expira_utc>UTC_TIMESTAMP(6)))))
 ) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Reserva no vigente para esta sesion'; END IF;
END$$
DROP PROCEDURE IF EXISTS sp_control_renovar$$
CREATE PROCEDURE sp_control_renovar(IN p_control BIGINT, IN p_sesion BIGINT, IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
 CALL sp_control_exigir(p_control,p_sesion,p_unidad);
 UPDATE sesiones_control c JOIN sesiones s ON s.id_sesion=c.id_sesion
 LEFT JOIN permisos_soporte p ON p.id_permiso=c.id_permiso
 SET c.expira_utc=LEAST(s.expira_utc,TIMESTAMPADD(SECOND,45,UTC_TIMESTAMP(6)),COALESCE(p.expira_utc,s.expira_utc)) WHERE c.id_control=p_control;
 SELECT id_control,expira_utc FROM sesiones_control WHERE id_control=p_control;
END$$
DROP PROCEDURE IF EXISTS sp_control_cerrar$$
CREATE PROCEDURE sp_control_cerrar(IN p_control BIGINT, IN p_motivo VARCHAR(30))
SQL SECURITY DEFINER
BEGIN
 DECLARE v_unidad INT DEFAULT NULL;
 DECLARE v_lock INT;
 DECLARE v_actor BIGINT;
 SELECT c.id_vehiculo,s.id_usuario INTO v_unidad,v_actor FROM sesiones_control c
 LEFT JOIN asignaciones a ON a.id_asignacion=c.id_asignacion JOIN sesiones s ON s.id_sesion=c.id_sesion
 WHERE c.id_control=p_control;
 IF v_unidad IS NULL OR p_motivo IS NULL OR p_motivo NOT IN ('CANCELADA','EXPIRADA','DESCONECTADA','REINICIO','REVOCADA') THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Reserva o motivo inexistente'; END IF;
 SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=v_unidad FOR UPDATE;
 IF EXISTS(SELECT 1 FROM reservas_control WHERE id_control=p_control) THEN
 UPDATE sesiones_control SET fin_utc=COALESCE(fin_utc,UTC_TIMESTAMP(6)),motivo_fin=COALESCE(motivo_fin,p_motivo) WHERE id_control=p_control;
 UPDATE reservas_control SET estado='DETENIENDO' WHERE id_control=p_control;
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
 VALUES(v_actor,IF(EXISTS(SELECT 1 FROM sesiones_control WHERE id_control=p_control AND id_asignacion IS NULL),'CERRAR_EMPRESA',IF(EXISTS(SELECT 1 FROM sesiones_control WHERE id_control=p_control AND id_permiso IS NOT NULL),'CERRAR_SOPORTE','CERRAR_COMPRADOR')),'vehiculo',CAST(v_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),JSON_OBJECT('id_control',p_control,'motivo',p_motivo));
 END IF;
 SELECT v_unidad AS id_vehiculo;
END$$
DROP PROCEDURE IF EXISTS sp_control_liberar$$
CREATE PROCEDURE sp_control_liberar(IN p_control BIGINT)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_unidad INT DEFAULT NULL;
 DECLARE v_lock INT;
 DECLARE v_actor BIGINT;
 SELECT c.id_vehiculo,s.id_usuario INTO v_unidad,v_actor FROM sesiones_control c
 LEFT JOIN asignaciones a ON a.id_asignacion=c.id_asignacion JOIN sesiones s ON s.id_sesion=c.id_sesion WHERE c.id_control=p_control;
 SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=v_unidad FOR UPDATE;
 IF NOT EXISTS(SELECT 1 FROM reservas_control r JOIN sesiones_control c ON c.id_control=r.id_control
 WHERE c.id_control=p_control AND r.estado='DETENIENDO' AND c.fin_utc IS NOT NULL) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Se requiere cierre y solicitud de DETENER antes de liberar'; END IF;
 -- Exclusivamente para el servicio, DESPUÉS de procesar DETENER y cancelar la demo.
 -- No acredita recepción física. Si la parada falla debe conservarse DETENIENDO.
 DELETE FROM reservas_control WHERE id_control=p_control;
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
 VALUES(v_actor,IF(EXISTS(SELECT 1 FROM sesiones_control WHERE id_control=p_control AND id_asignacion IS NULL),'LIBERAR_EMPRESA',IF(EXISTS(SELECT 1 FROM sesiones_control WHERE id_control=p_control AND id_permiso IS NOT NULL),'LIBERAR_SOPORTE','LIBERAR_COMPRADOR')),'vehiculo',CAST(v_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),JSON_OBJECT('id_control',p_control));
END$$
DROP PROCEDURE IF EXISTS sp_control_reservas$$
CREATE PROCEDURE sp_control_reservas()
SQL SECURITY DEFINER
BEGIN
 SELECT r.id_vehiculo,r.estado,c.id_control,c.id_sesion,c.expira_utc,c.fin_utc,
 (c.fin_utc IS NOT NULL OR c.expira_utc<=UTC_TIMESTAMP(6) OR s.revocada_utc IS NOT NULL
 OR s.expira_utc<=UTC_TIMESTAMP(6) OR u.activo=0 OR v.activo=0 OR NOT COALESCE(
 ((c.id_asignacion IS NULL AND c.id_permiso IS NULL AND u.rol='ADMINISTRADOR'
 AND NOT EXISTS(SELECT 1 FROM asignaciones actual WHERE actual.id_vehiculo=r.id_vehiculo AND actual.fin_utc IS NULL))
 OR (a.id_asignacion IS NOT NULL AND a.fin_utc IS NULL AND a.id_vehiculo=r.id_vehiculo
 AND propietario.activo=1 AND propietario.rol='USUARIO'
 AND ((u.rol='USUARIO' AND a.id_usuario=s.id_usuario AND c.id_permiso IS NULL)
 OR (u.rol='ADMINISTRADOR' AND p.id_administrador=s.id_usuario AND p.id_asignacion=c.id_asignacion
 AND p.operativo=1 AND p.revocado_utc IS NULL AND p.expira_utc>UTC_TIMESTAMP(6))))),0)) AS cierre_pendiente
 FROM reservas_control r JOIN sesiones_control c ON c.id_control=r.id_control
 JOIN sesiones s ON s.id_sesion=c.id_sesion JOIN usuarios u ON u.id_usuario=s.id_usuario
 JOIN vehiculos v ON v.id_vehiculo=c.id_vehiculo AND v.id_vehiculo=r.id_vehiculo
 LEFT JOIN asignaciones a ON a.id_asignacion=c.id_asignacion
 LEFT JOIN usuarios propietario ON propietario.id_usuario=a.id_usuario
 LEFT JOIN permisos_soporte p ON p.id_permiso=c.id_permiso;
END$$
DROP PROCEDURE IF EXISTS sp_control_contexto$$
CREATE PROCEDURE sp_control_contexto(IN p_control BIGINT, IN p_sesion BIGINT)
SQL SECURITY DEFINER
BEGIN
 SELECT c.id_control,c.id_sesion,c.id_vehiculo,c.expira_utc,c.fin_utc,r.estado,
 IF(r.id_control IS NULL,0,1) AS reserva_pendiente
 FROM sesiones_control c LEFT JOIN reservas_control r ON r.id_control=c.id_control
 WHERE c.id_control=p_control AND c.id_sesion=p_sesion;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('019_control_empresa');
