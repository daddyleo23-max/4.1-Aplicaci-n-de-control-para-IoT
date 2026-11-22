-- Base de exclusividad por sesión del comprador. Primero sobre copia con 001–013.
-- No activa reservas automáticamente: la integración HTTP/WSS es una entrega posterior.
-- DDL puede producir commits implícitos. No repetir ante error parcial.
CREATE TABLE sesiones_control (
 id_control BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 id_sesion BIGINT NOT NULL,
 id_asignacion BIGINT NOT NULL,
 inicio_utc DATETIME(6) NOT NULL,
 expira_utc DATETIME(6) NOT NULL,
 fin_utc DATETIME(6) NULL,
 motivo_fin VARCHAR(30) NULL,
 INDEX idx_control_pendiente(fin_utc,expira_utc),
 FOREIGN KEY(id_sesion) REFERENCES sesiones(id_sesion) ON DELETE RESTRICT,
 FOREIGN KEY(id_asignacion) REFERENCES asignaciones(id_asignacion) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
ALTER TABLE reservas_control
 MODIFY id_sesion_invitado BIGINT NULL,
 ADD COLUMN id_control BIGINT NULL,
 ADD UNIQUE KEY uq_reserva_control(id_control),
 ADD CONSTRAINT fk_reserva_control FOREIGN KEY(id_control) REFERENCES sesiones_control(id_control) ON DELETE RESTRICT,
 ADD CONSTRAINT ck_reserva_titular CHECK (
  (id_sesion_invitado IS NOT NULL AND id_control IS NULL)
  OR (id_sesion_invitado IS NULL AND id_control IS NOT NULL)
 );
DELIMITER $$
CREATE PROCEDURE sp_control_adquirir(IN p_sesion BIGINT, IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_lock INT DEFAULT NULL;
 DECLARE v_asignacion BIGINT DEFAULT NULL;
 DECLARE v_actor BIGINT DEFAULT NULL;
 DECLARE v_expira DATETIME(6);
 DECLARE v_control BIGINT;
 SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=p_unidad AND activo=1 FOR UPDATE;
 SELECT a.id_asignacion,s.id_usuario,LEAST(s.expira_utc,TIMESTAMPADD(SECOND,45,UTC_TIMESTAMP(6)))
 INTO v_asignacion,v_actor,v_expira
 FROM sesiones s JOIN usuarios u ON u.id_usuario=s.id_usuario AND u.activo=1 AND u.rol='USUARIO'
 JOIN asignaciones a ON a.id_usuario=u.id_usuario AND a.id_vehiculo=v_lock AND a.fin_utc IS NULL
 WHERE s.id_sesion=p_sesion AND s.revocada_utc IS NULL AND s.expira_utc>UTC_TIMESTAMP(6);
 IF v_asignacion IS NULL OR NOT EXISTS(SELECT 1 FROM comandos WHERE id_vehiculo=p_unidad AND nombre='DETENER' AND activo=1) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Sesion, propiedad o DETENER incompatibles'; END IF;
 IF EXISTS(SELECT 1 FROM reservas_control WHERE id_vehiculo=p_unidad) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La unidad conserva otra reserva o detencion pendiente'; END IF;
 INSERT INTO sesiones_control(id_sesion,id_asignacion,inicio_utc,expira_utc)
 VALUES(p_sesion,v_asignacion,UTC_TIMESTAMP(6),v_expira);
 SET v_control=LAST_INSERT_ID();
 INSERT INTO reservas_control(id_vehiculo,id_control,creada_utc) VALUES(p_unidad,v_control,UTC_TIMESTAMP(6));
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
 VALUES(v_actor,'RESERVAR_COMPRADOR','vehiculo',CAST(p_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),JSON_OBJECT('id_control',v_control));
 SELECT v_control AS id_control,p_unidad AS id_vehiculo,v_expira AS expira_utc;
END$$
CREATE PROCEDURE sp_control_exigir(IN p_control BIGINT, IN p_sesion BIGINT, IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_lock INT;
 SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=p_unidad FOR UPDATE;
 IF NOT EXISTS(
 SELECT 1 FROM reservas_control r JOIN sesiones_control c ON c.id_control=r.id_control
 JOIN sesiones s ON s.id_sesion=c.id_sesion AND s.revocada_utc IS NULL AND s.expira_utc>UTC_TIMESTAMP(6)
 JOIN usuarios u ON u.id_usuario=s.id_usuario AND u.activo=1 AND u.rol='USUARIO'
 JOIN asignaciones a ON a.id_asignacion=c.id_asignacion AND a.fin_utc IS NULL AND a.id_usuario=u.id_usuario
 JOIN vehiculos v ON v.id_vehiculo=a.id_vehiculo AND v.activo=1
 WHERE a.id_vehiculo=r.id_vehiculo AND r.id_vehiculo=p_unidad AND c.id_control=p_control AND c.id_sesion=p_sesion AND r.estado='ACTIVA'
 AND c.fin_utc IS NULL AND c.expira_utc>UTC_TIMESTAMP(6)
 ) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Reserva no vigente para esta sesion'; END IF;
END$$
CREATE PROCEDURE sp_control_renovar(IN p_control BIGINT, IN p_sesion BIGINT, IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
 CALL sp_control_exigir(p_control,p_sesion,p_unidad);
 UPDATE sesiones_control c JOIN sesiones s ON s.id_sesion=c.id_sesion
 SET c.expira_utc=LEAST(s.expira_utc,TIMESTAMPADD(SECOND,45,UTC_TIMESTAMP(6))) WHERE c.id_control=p_control;
 SELECT id_control,expira_utc FROM sesiones_control WHERE id_control=p_control;
END$$
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
 VALUES(v_actor,'CERRAR_COMPRADOR','vehiculo',CAST(v_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),JSON_OBJECT('id_control',p_control,'motivo',p_motivo));
 END IF;
 SELECT v_unidad AS id_vehiculo;
END$$
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
 VALUES(v_actor,'LIBERAR_COMPRADOR','vehiculo',CAST(v_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),JSON_OBJECT('id_control',p_control));
END$$
CREATE PROCEDURE sp_control_reservas()
SQL SECURITY DEFINER
BEGIN
 SELECT r.id_vehiculo,r.estado,c.id_control,c.id_sesion,c.expira_utc,c.fin_utc,
 (c.fin_utc IS NOT NULL OR c.expira_utc<=UTC_TIMESTAMP(6) OR s.revocada_utc IS NOT NULL
 OR s.expira_utc<=UTC_TIMESTAMP(6) OR u.activo=0 OR u.rol<>'USUARIO' OR v.activo=0
 OR a.fin_utc IS NOT NULL OR a.id_usuario<>s.id_usuario) AS cierre_pendiente
 FROM reservas_control r JOIN sesiones_control c ON c.id_control=r.id_control
 JOIN sesiones s ON s.id_sesion=c.id_sesion JOIN usuarios u ON u.id_usuario=s.id_usuario
 JOIN asignaciones a ON a.id_asignacion=c.id_asignacion JOIN vehiculos v ON v.id_vehiculo=r.id_vehiculo;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('014_reservas_comprador');
