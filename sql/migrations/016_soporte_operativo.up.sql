-- Soporte operativo explícito; permisos anteriores conservan sólo MONITOREO.
-- Requiere copia con 001–015. DROP/CREATE sólo de rutinas nuevas de control.
-- Cerrar reservas antes de aplicar; DDL puede quedar parcial ante error.
ALTER TABLE permisos_soporte ADD COLUMN operativo TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE sesiones_control ADD COLUMN id_permiso BIGINT NULL,
 ADD CONSTRAINT fk_control_permiso FOREIGN KEY(id_permiso) REFERENCES permisos_soporte(id_permiso) ON DELETE RESTRICT;
DELIMITER $$
CREATE PROCEDURE sp_soporte_conceder_operativo(IN p_actor BIGINT, IN p_unidad INT, IN p_admin BIGINT, IN p_minutos INT)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_permiso BIGINT;
 -- La rutina previa bloquea la unidad y valida propietario y destinatario.
 CALL sp_soporte_conceder(p_actor,p_unidad,p_admin,p_minutos);
 SELECT MAX(p.id_permiso) INTO v_permiso FROM permisos_soporte p JOIN asignaciones a ON a.id_asignacion=p.id_asignacion
 WHERE a.id_vehiculo=p_unidad AND a.fin_utc IS NULL AND a.id_usuario=p_actor AND p.id_administrador=p_admin;
 UPDATE permisos_soporte SET operativo=1 WHERE id_permiso=v_permiso;
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
 VALUES(p_actor,'AUTORIZAR_SOPORTE_OPERATIVO','vehiculo',CAST(p_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),JSON_OBJECT('id_permiso',v_permiso));
END$$
CREATE PROCEDURE sp_soporte_operar_acceso(IN p_admin BIGINT, IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
 SELECT p.id_permiso FROM permisos_soporte p
 JOIN asignaciones a ON a.id_asignacion=p.id_asignacion AND a.fin_utc IS NULL
 JOIN vehiculos v ON v.id_vehiculo=a.id_vehiculo AND v.activo=1
 JOIN usuarios u ON u.id_usuario=a.id_usuario AND u.activo=1 AND u.rol='USUARIO'
 JOIN usuarios ad ON ad.id_usuario=p.id_administrador AND ad.activo=1 AND ad.rol='ADMINISTRADOR'
 WHERE p.id_administrador=p_admin AND a.id_vehiculo=p_unidad AND p.operativo=1
 AND p.revocado_utc IS NULL AND p.expira_utc>UTC_TIMESTAMP(6) LIMIT 1;
END$$
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
 JOIN usuarios propietario ON propietario.id_usuario=a.id_usuario AND propietario.activo=1 AND propietario.rol='USUARIO'
 LEFT JOIN permisos_soporte p ON p.id_asignacion=a.id_asignacion AND p.id_administrador=u.id_usuario
 AND p.operativo=1 AND p.revocado_utc IS NULL AND p.expira_utc>UTC_TIMESTAMP(6)
 WHERE s.id_sesion=p_sesion AND s.revocada_utc IS NULL AND s.expira_utc>UTC_TIMESTAMP(6)
 AND ((u.rol='USUARIO' AND a.id_usuario=u.id_usuario) OR (u.rol='ADMINISTRADOR' AND p.id_permiso IS NOT NULL))
 ORDER BY p.id_permiso DESC LIMIT 1;
 IF v_asignacion IS NULL OR NOT EXISTS(SELECT 1 FROM comandos WHERE id_vehiculo=p_unidad AND nombre='DETENER' AND activo=1) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Sesion, propiedad o DETENER incompatibles'; END IF;
 IF EXISTS(SELECT 1 FROM reservas_control WHERE id_vehiculo=p_unidad) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La unidad conserva otra reserva o detencion pendiente'; END IF;
 INSERT INTO sesiones_control(id_sesion,id_asignacion,id_permiso,inicio_utc,expira_utc)
 VALUES(p_sesion,v_asignacion,v_permiso,UTC_TIMESTAMP(6),v_expira);
 SET v_control=LAST_INSERT_ID();
 INSERT INTO reservas_control(id_vehiculo,id_control,creada_utc) VALUES(p_unidad,v_control,UTC_TIMESTAMP(6));
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
 VALUES(v_actor,IF(v_permiso IS NULL,'RESERVAR_COMPRADOR','RESERVAR_SOPORTE'),'vehiculo',CAST(p_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),JSON_OBJECT('id_control',v_control));
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
 JOIN asignaciones a ON a.id_asignacion=c.id_asignacion AND a.fin_utc IS NULL
 JOIN usuarios propietario ON propietario.id_usuario=a.id_usuario AND propietario.activo=1 AND propietario.rol='USUARIO'
 LEFT JOIN permisos_soporte p ON p.id_permiso=c.id_permiso AND p.id_asignacion=a.id_asignacion
 JOIN vehiculos v ON v.id_vehiculo=a.id_vehiculo AND v.activo=1
 WHERE a.id_vehiculo=r.id_vehiculo AND r.id_vehiculo=p_unidad AND c.id_control=p_control AND c.id_sesion=p_sesion AND r.estado='ACTIVA'
 AND c.fin_utc IS NULL AND c.expira_utc>UTC_TIMESTAMP(6)
 AND ((u.rol='USUARIO' AND a.id_usuario=u.id_usuario AND c.id_permiso IS NULL)
 OR (u.rol='ADMINISTRADOR' AND p.id_administrador=u.id_usuario AND p.operativo=1
 AND p.revocado_utc IS NULL AND p.expira_utc>UTC_TIMESTAMP(6)))
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
 SELECT a.id_vehiculo,s.id_usuario INTO v_unidad,v_actor FROM sesiones_control c
 JOIN asignaciones a ON a.id_asignacion=c.id_asignacion JOIN sesiones s ON s.id_sesion=c.id_sesion
 WHERE c.id_control=p_control;
 IF v_unidad IS NULL OR p_motivo IS NULL OR p_motivo NOT IN ('CANCELADA','EXPIRADA','DESCONECTADA','REINICIO','REVOCADA') THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Reserva o motivo inexistente'; END IF;
 SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=v_unidad FOR UPDATE;
 IF EXISTS(SELECT 1 FROM reservas_control WHERE id_control=p_control) THEN
 UPDATE sesiones_control SET fin_utc=COALESCE(fin_utc,UTC_TIMESTAMP(6)),motivo_fin=COALESCE(motivo_fin,p_motivo) WHERE id_control=p_control;
 UPDATE reservas_control SET estado='DETENIENDO' WHERE id_control=p_control;
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
 VALUES(v_actor,IF(EXISTS(SELECT 1 FROM sesiones_control WHERE id_control=p_control AND id_permiso IS NOT NULL),'CERRAR_SOPORTE','CERRAR_COMPRADOR'),'vehiculo',CAST(v_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),JSON_OBJECT('id_control',p_control,'motivo',p_motivo));
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
 SELECT a.id_vehiculo,s.id_usuario INTO v_unidad,v_actor FROM sesiones_control c
 JOIN asignaciones a ON a.id_asignacion=c.id_asignacion JOIN sesiones s ON s.id_sesion=c.id_sesion WHERE c.id_control=p_control;
 SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=v_unidad FOR UPDATE;
 IF NOT EXISTS(SELECT 1 FROM reservas_control r JOIN sesiones_control c ON c.id_control=r.id_control
 WHERE c.id_control=p_control AND r.estado='DETENIENDO' AND c.fin_utc IS NOT NULL) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Se requiere cierre y solicitud de DETENER antes de liberar'; END IF;
 -- Exclusivamente para el servicio, DESPUÉS de procesar DETENER y cancelar la demo.
 -- No acredita recepción física. Si la parada falla debe conservarse DETENIENDO.
 DELETE FROM reservas_control WHERE id_control=p_control;
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
 VALUES(v_actor,IF(EXISTS(SELECT 1 FROM sesiones_control WHERE id_control=p_control AND id_permiso IS NOT NULL),'LIBERAR_SOPORTE','LIBERAR_COMPRADOR'),'vehiculo',CAST(v_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),JSON_OBJECT('id_control',p_control));
END$$
DROP PROCEDURE IF EXISTS sp_control_reservas$$
CREATE PROCEDURE sp_control_reservas()
SQL SECURITY DEFINER
BEGIN
 SELECT r.id_vehiculo,r.estado,c.id_control,c.id_sesion,c.expira_utc,c.fin_utc,
 (c.fin_utc IS NOT NULL OR c.expira_utc<=UTC_TIMESTAMP(6) OR s.revocada_utc IS NOT NULL
 OR s.expira_utc<=UTC_TIMESTAMP(6) OR u.activo=0 OR v.activo=0 OR a.fin_utc IS NOT NULL
 OR propietario.activo=0 OR propietario.rol<>'USUARIO'
 OR NOT ((u.rol='USUARIO' AND a.id_usuario=s.id_usuario AND c.id_permiso IS NULL)
 OR (u.rol='ADMINISTRADOR' AND p.id_permiso IS NOT NULL AND p.id_administrador=s.id_usuario
 AND p.id_asignacion=c.id_asignacion AND p.operativo=1 AND p.revocado_utc IS NULL AND p.expira_utc>UTC_TIMESTAMP(6)))) AS cierre_pendiente
 FROM reservas_control r JOIN sesiones_control c ON c.id_control=r.id_control
 JOIN sesiones s ON s.id_sesion=c.id_sesion JOIN usuarios u ON u.id_usuario=s.id_usuario
 JOIN asignaciones a ON a.id_asignacion=c.id_asignacion JOIN vehiculos v ON v.id_vehiculo=r.id_vehiculo
 JOIN usuarios propietario ON propietario.id_usuario=a.id_usuario
 LEFT JOIN permisos_soporte p ON p.id_permiso=c.id_permiso;
END$$
DROP PROCEDURE IF EXISTS sp_soporte_listar$$
CREATE PROCEDURE sp_soporte_listar(IN p_actor BIGINT, IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
 SELECT p.id_permiso,p.operativo,p.id_administrador,ad.nombre AS administrador,p.creado_utc,p.expira_utc,p.revocado_utc,
 (p.revocado_utc IS NULL AND p.expira_utc>UTC_TIMESTAMP(6) AND a.fin_utc IS NULL) AS vigente
 FROM permisos_soporte p JOIN asignaciones a ON a.id_asignacion=p.id_asignacion
 JOIN usuarios ad ON ad.id_usuario=p.id_administrador
 WHERE a.id_vehiculo=p_unidad AND (a.id_usuario=p_actor OR p.id_administrador=p_actor)
 ORDER BY p.id_permiso DESC LIMIT 100;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('016_soporte_operativo');
