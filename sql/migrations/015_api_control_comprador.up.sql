-- Integración API de reservas del comprador. Requiere 014 validada.
DELIMITER $$
CREATE PROCEDURE sp_control_contexto(IN p_control BIGINT, IN p_sesion BIGINT)
SQL SECURITY DEFINER
BEGIN
 SELECT c.id_control,c.id_sesion,a.id_vehiculo,c.expira_utc,c.fin_utc,r.estado,
 IF(r.id_control IS NULL,0,1) AS reserva_pendiente
 FROM sesiones_control c JOIN asignaciones a ON a.id_asignacion=c.id_asignacion
 LEFT JOIN reservas_control r ON r.id_control=c.id_control
 WHERE c.id_control=p_control AND c.id_sesion=p_sesion;
END$$
CREATE PROCEDURE sp_control_mover(IN p_control BIGINT, IN p_sesion BIGINT, IN p_unidad INT, IN p_comando INT)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_comando INT DEFAULT NULL;
 DECLARE v_conectado TINYINT DEFAULT 0;
 CALL sp_control_exigir(p_control,p_sesion,p_unidad);
 SELECT id_comando INTO v_comando FROM comandos WHERE id_comando=p_comando AND id_vehiculo=p_unidad AND activo=1 AND nombre<>'DEMO';
 IF v_comando IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Comando incompatible'; END IF;
 SELECT conectado INTO v_conectado FROM estado_vehiculo WHERE id_vehiculo=p_unidad;
 CALL sp_actualizar_estado(p_unidad,v_comando,COALESCE(v_conectado,0));
 CALL sp_registrar_historial(p_unidad,v_comando,'MANUAL');
 SELECT p_unidad AS id_vehiculo,id_comando,nombre AS comando,codigo FROM comandos WHERE id_comando=v_comando;
END$$
CREATE PROCEDURE sp_control_detener(IN p_control BIGINT)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_unidad INT DEFAULT NULL;
 DECLARE v_lock INT;
 DECLARE v_comando INT DEFAULT NULL;
 DECLARE v_conectado TINYINT DEFAULT 0;
 SELECT id_vehiculo INTO v_unidad FROM reservas_control WHERE id_control=p_control;
 SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=v_unidad FOR UPDATE;
 IF NOT EXISTS(SELECT 1 FROM reservas_control WHERE id_control=p_control AND id_vehiculo=v_unidad) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La reserva no existe'; END IF;
 SELECT MIN(id_comando) INTO v_comando FROM comandos WHERE id_vehiculo=v_unidad AND nombre='DETENER' AND activo=1;
 IF v_comando IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Falta DETENER activo'; END IF;
 SELECT conectado INTO v_conectado FROM estado_vehiculo WHERE id_vehiculo=v_unidad;
 CALL sp_actualizar_estado(v_unidad,v_comando,COALESCE(v_conectado,0));
 CALL sp_registrar_historial(v_unidad,v_comando,'MANUAL');
 SELECT v_unidad AS id_vehiculo,id_comando,nombre AS comando,codigo FROM comandos WHERE id_comando=v_comando;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('015_api_control_comprador');
