-- Complemento de 011. Sólo rutinas; sin triggers nuevos ni cambios de datos.
DELIMITER $$
CREATE PROCEDURE sp_invitado_identificar(IN p_hash BINARY(32))
SQL SECURITY DEFINER
BEGIN
    SELECT s.id_sesion_invitado,s.id_vehiculo,s.expira_utc,s.fin_utc,s.motivo_fin,
           IF(r.id_sesion_invitado IS NULL,0,1) AS reserva_pendiente
    FROM sesiones_invitado s LEFT JOIN reservas_control r ON r.id_sesion_invitado=s.id_sesion_invitado
    WHERE s.token_hash=p_hash;
END$$

CREATE PROCEDURE sp_invitado_sesion_id(IN p_sesion BIGINT)
SQL SECURITY DEFINER
BEGIN
    SELECT s.id_sesion_invitado,s.id_vehiculo,s.expira_utc,s.fin_utc,
           IF(r.id_sesion_invitado IS NULL,0,1) AS reserva_pendiente
    FROM sesiones_invitado s LEFT JOIN reservas_control r ON r.id_sesion_invitado=s.id_sesion_invitado
    WHERE s.id_sesion_invitado=p_sesion;
END$$

CREATE PROCEDURE sp_invitado_reservas_actuales()
SQL SECURITY DEFINER
BEGIN
    SELECT s.id_sesion_invitado,s.id_vehiculo FROM reservas_control r
    JOIN sesiones_invitado s ON s.id_sesion_invitado=r.id_sesion_invitado;
END$$

CREATE PROCEDURE sp_invitado_configuracion(IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
    SELECT cfg.id_vehiculo,cfg.habilitada,cfg.duracion_s,cfg.pulso_ms,
        (SELECT JSON_ARRAYAGG(ci.id_comando) FROM comandos_invitado ci WHERE ci.id_vehiculo=p_unidad) AS comandos
    FROM configuracion_invitados cfg WHERE cfg.id_vehiculo=p_unidad;
END$$

CREATE PROCEDURE sp_invitado_unidades(IN p_modelo INT)
SQL SECURITY DEFINER
BEGIN
    SELECT v.id_vehiculo,v.nombre,cfg.duracion_s,cfg.pulso_ms,
        IF(r.id_vehiculo IS NULL,0,1) AS ocupada
    FROM vehiculos v JOIN modelos m ON m.id_modelo=v.id_modelo AND m.activo=1 AND m.publico=1
    JOIN configuracion_invitados cfg ON cfg.id_vehiculo=v.id_vehiculo AND cfg.habilitada=1
    LEFT JOIN reservas_control r ON r.id_vehiculo=v.id_vehiculo
    WHERE m.id_modelo=p_modelo AND v.activo=1 AND v.estado_comercial='EXHIBICION'
        AND NOT EXISTS(SELECT 1 FROM asignaciones a WHERE a.id_vehiculo=v.id_vehiculo AND a.fin_utc IS NULL)
        AND EXISTS(SELECT 1 FROM comandos_invitado ci JOIN comandos c ON c.id_comando=ci.id_comando
            WHERE ci.id_vehiculo=v.id_vehiculo AND c.id_vehiculo=v.id_vehiculo AND c.activo=1 AND c.nombre='DETENER')
    ORDER BY v.id_vehiculo;
END$$

CREATE PROCEDURE sp_reserva_exigir_libre(IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_id INT DEFAULT NULL;
    SELECT id_vehiculo INTO v_id FROM vehiculos WHERE id_vehiculo=p_unidad FOR UPDATE;
    IF v_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unidad inexistente';
    END IF;
    IF EXISTS(SELECT 1 FROM reservas_control WHERE id_vehiculo=p_unidad) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La unidad tiene una reserva de Invitado';
    END IF;
END$$

CREATE PROCEDURE sp_invitado_mover(IN p_hash BINARY(32), IN p_comando INT)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_unidad INT DEFAULT NULL;
    DECLARE v_lock INT;
    DECLARE v_id INT DEFAULT NULL;
    DECLARE v_nombre VARCHAR(60);
    DECLARE v_codigo INT;
    DECLARE v_pulso INT;
    DECLARE v_expira DATETIME(6);
    DECLARE v_conectado INT DEFAULT 0;
    SELECT id_vehiculo INTO v_unidad FROM sesiones_invitado WHERE token_hash=p_hash;
    IF v_unidad IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Sesion de Invitado no valida';
    END IF;
    SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=v_unidad FOR UPDATE;
    SELECT c.id_comando,c.nombre,c.codigo,cfg.pulso_ms,s.expira_utc
    INTO v_id,v_nombre,v_codigo,v_pulso,v_expira
    FROM sesiones_invitado s
    JOIN reservas_control r ON r.id_sesion_invitado=s.id_sesion_invitado AND r.id_vehiculo=s.id_vehiculo AND r.estado='ACTIVA'
    JOIN configuracion_invitados cfg ON cfg.id_vehiculo=s.id_vehiculo AND cfg.habilitada=1
    JOIN comandos_invitado ci ON ci.id_vehiculo=s.id_vehiculo AND ci.id_comando=p_comando
    JOIN comandos c ON c.id_comando=ci.id_comando AND c.id_vehiculo=s.id_vehiculo AND c.activo=1
    JOIN vehiculos v ON v.id_vehiculo=s.id_vehiculo AND v.activo=1 AND v.estado_comercial='EXHIBICION'
    JOIN modelos m ON m.id_modelo=v.id_modelo AND m.activo=1 AND m.publico=1
    WHERE s.token_hash=p_hash AND s.fin_utc IS NULL AND s.expira_utc>UTC_TIMESTAMP(6)
        AND NOT EXISTS(SELECT 1 FROM asignaciones a WHERE a.id_vehiculo=s.id_vehiculo AND a.fin_utc IS NULL)
        AND c.nombre IN ('ADELANTE','ATRAS','GIRAR_IZQUIERDA','GIRAR_DERECHA',
            'SUBIR_HORQUILLA','BAJAR_HORQUILLA','LUCES','SONIDO','VELOCIDAD','DETENER');
    IF v_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Sesion vencida o comando no autorizado';
    END IF;
    SET v_conectado=COALESCE((SELECT conectado FROM estado_vehiculo WHERE id_vehiculo=v_unidad),0);
    CALL sp_actualizar_estado(v_unidad,v_id,v_conectado);
    CALL sp_registrar_historial(v_unidad,v_id,'MANUAL');
    SELECT v_unidad AS id_vehiculo,v_id AS id_comando,v_nombre AS comando,v_codigo AS codigo,
           LEAST(v_pulso,GREATEST(0,TIMESTAMPDIFF(MICROSECOND,UTC_TIMESTAMP(6),v_expira) DIV 1000)) AS pulso_ms;
END$$

CREATE PROCEDURE sp_invitado_detener(IN p_sesion BIGINT)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_unidad INT DEFAULT NULL;
    DECLARE v_lock INT;
    DECLARE v_id INT DEFAULT NULL;
    DECLARE v_codigo INT;
    DECLARE v_conectado INT DEFAULT 0;
    SELECT id_vehiculo INTO v_unidad FROM sesiones_invitado WHERE id_sesion_invitado=p_sesion;
    IF v_unidad IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Sesion inexistente';
    END IF;
    SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=v_unidad FOR UPDATE;
    IF NOT EXISTS(SELECT 1 FROM reservas_control WHERE id_vehiculo=v_unidad AND id_sesion_invitado=p_sesion) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La reserva ya no pertenece a esta sesion';
    END IF;
    SELECT c.id_comando,c.codigo INTO v_id,v_codigo FROM comandos c
    JOIN comandos_invitado ci ON ci.id_comando=c.id_comando AND ci.id_vehiculo=v_unidad
    WHERE c.id_vehiculo=v_unidad AND c.activo=1 AND c.nombre='DETENER';
    IF v_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='No se pudo solicitar DETENER';
    END IF;
    SET v_conectado=COALESCE((SELECT conectado FROM estado_vehiculo WHERE id_vehiculo=v_unidad),0);
    CALL sp_actualizar_estado(v_unidad,v_id,v_conectado);
    SELECT v_unidad AS id_vehiculo,v_id AS id_comando,'DETENER' AS comando,v_codigo AS codigo;
END$$
CREATE PROCEDURE sp_invitado_cerrar_admin(IN p_actor BIGINT, IN p_sesion BIGINT)
SQL SECURITY DEFINER
BEGIN
    CALL sp_invitado_cerrar(p_sesion,'REVOCADA');
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
    VALUES(p_actor,'REVOCAR_INVITADO','sesion_invitado',CAST(p_sesion AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('012_api_invitados');
