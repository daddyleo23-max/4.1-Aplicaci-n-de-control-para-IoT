-- Base de reservas. Aplicar después de 010, primero en copia aislada.
-- No habilita endpoints de Invitado. DDL con commit implícito.
CREATE TABLE configuracion_invitados (
    id_vehiculo INT NOT NULL PRIMARY KEY,
    habilitada BOOLEAN NOT NULL DEFAULT 0,
    duracion_s SMALLINT UNSIGNED NOT NULL DEFAULT 60,
    pulso_ms SMALLINT UNSIGNED NOT NULL DEFAULT 300,
    actualizado_por BIGINT NOT NULL,
    actualizado_utc DATETIME(6) NOT NULL,
    CONSTRAINT fk_cfg_inv_unidad FOREIGN KEY(id_vehiculo) REFERENCES vehiculos(id_vehiculo) ON DELETE RESTRICT,
    CONSTRAINT fk_cfg_inv_actor FOREIGN KEY(actualizado_por) REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
    CONSTRAINT ck_cfg_inv_habilitada CHECK(habilitada IN (0,1)),
    CONSTRAINT ck_cfg_inv_duracion CHECK(duracion_s BETWEEN 15 AND 120),
    CONSTRAINT ck_cfg_inv_pulso CHECK(pulso_ms BETWEEN 50 AND 500)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE comandos_invitado (
    id_vehiculo INT NOT NULL,
    id_comando INT NOT NULL,
    PRIMARY KEY(id_vehiculo,id_comando),
    CONSTRAINT fk_cmd_inv_cfg FOREIGN KEY(id_vehiculo) REFERENCES configuracion_invitados(id_vehiculo) ON DELETE RESTRICT,
    CONSTRAINT fk_cmd_inv_comando FOREIGN KEY(id_comando) REFERENCES comandos(id_comando) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE sesiones_invitado (
    id_sesion_invitado BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_vehiculo INT NOT NULL,
    token_hash BINARY(32) NOT NULL,
    inicio_utc DATETIME(6) NOT NULL,
    expira_utc DATETIME(6) NOT NULL,
    fin_utc DATETIME(6) DEFAULT NULL,
    motivo_fin ENUM('CANCELADA','EXPIRADA','DESCONECTADA','REINICIO','REVOCADA') DEFAULT NULL,
    UNIQUE KEY uq_sesion_inv_token(token_hash),
    KEY idx_sesion_inv_expira(fin_utc,expira_utc),
    CONSTRAINT fk_sesion_inv_unidad FOREIGN KEY(id_vehiculo) REFERENCES vehiculos(id_vehiculo) ON DELETE RESTRICT,
    CONSTRAINT ck_sesion_inv_fechas CHECK(expira_utc>inicio_utc AND (fin_utc IS NULL OR fin_utc>=inicio_utc))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE reservas_control (
    id_vehiculo INT NOT NULL PRIMARY KEY,
    id_sesion_invitado BIGINT NOT NULL,
    estado ENUM('ACTIVA','DETENIENDO') NOT NULL DEFAULT 'ACTIVA',
    creada_utc DATETIME(6) NOT NULL,
    UNIQUE KEY uq_reserva_sesion_inv(id_sesion_invitado),
    CONSTRAINT fk_reserva_unidad FOREIGN KEY(id_vehiculo) REFERENCES vehiculos(id_vehiculo) ON DELETE RESTRICT,
    CONSTRAINT fk_reserva_sesion_inv FOREIGN KEY(id_sesion_invitado) REFERENCES sesiones_invitado(id_sesion_invitado) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DELIMITER $$
CREATE PROCEDURE sp_invitado_configurar(
    IN p_actor BIGINT, IN p_unidad INT, IN p_habilitada BOOLEAN,
    IN p_duracion INT, IN p_pulso INT, IN p_comandos JSON
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_id INT DEFAULT NULL;
    DECLARE v_modelo INT;
    DECLARE v_activo INT;
    DECLARE v_estado VARCHAR(20);
    DECLARE v_count INT;
    SELECT id_vehiculo,id_modelo,activo,estado_comercial INTO v_id,v_modelo,v_activo,v_estado
    FROM vehiculos WHERE id_vehiculo=p_unidad FOR UPDATE;
    IF v_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unidad inexistente';
    END IF;
    IF EXISTS(SELECT 1 FROM reservas_control WHERE id_vehiculo=p_unidad) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Finaliza la reserva antes de cambiar sus limites';
    END IF;
    IF p_habilitada=1 AND (v_activo<>1 OR v_estado<>'EXHIBICION'
       OR NOT EXISTS(SELECT 1 FROM modelos WHERE id_modelo=v_modelo AND activo=1 AND publico=1)
       OR EXISTS(SELECT 1 FROM asignaciones WHERE id_vehiculo=p_unidad AND fin_utc IS NULL)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Se requiere exhibicion activa publicada y sin propietario';
    END IF;
    IF p_habilitada IS NULL OR p_habilitada NOT IN (0,1) OR p_duracion IS NULL OR p_duracion NOT BETWEEN 15 AND 120
       OR p_pulso IS NULL OR p_pulso NOT BETWEEN 50 AND 500 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Limites de prueba fuera de rango';
    END IF;
    IF p_comandos IS NULL OR JSON_TYPE(p_comandos)<>'ARRAY' OR JSON_LENGTH(p_comandos) NOT BETWEEN 1 AND 10 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Selecciona entre uno y diez comandos';
    END IF;
    IF EXISTS(SELECT 1 FROM JSON_TABLE(p_comandos,'$[*]' COLUMNS(pos FOR ORDINALITY)) j
        WHERE JSON_TYPE(JSON_EXTRACT(p_comandos,CONCAT('$[',j.pos-1,']')))<>'INTEGER') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Los identificadores de comando deben ser enteros';
    END IF;
    SELECT COUNT(DISTINCT c.id_comando) INTO v_count
    FROM JSON_TABLE(p_comandos,'$[*]' COLUMNS(id_comando INT PATH '$' ERROR ON EMPTY ERROR ON ERROR)) j
    JOIN comandos c ON c.id_comando=j.id_comando AND c.id_vehiculo=p_unidad AND c.activo=1
    WHERE c.nombre IN ('ADELANTE','ATRAS','GIRAR_IZQUIERDA','GIRAR_DERECHA',
        'SUBIR_HORQUILLA','BAJAR_HORQUILLA','LUCES','SONIDO','VELOCIDAD','DETENER');
    IF v_count<>JSON_LENGTH(p_comandos) OR NOT EXISTS(
        SELECT 1 FROM comandos c
        JOIN JSON_TABLE(p_comandos,'$[*]' COLUMNS(id_comando INT PATH '$')) j ON j.id_comando=c.id_comando
        WHERE c.id_vehiculo=p_unidad AND c.activo=1 AND c.nombre='DETENER'
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Comandos incompatibles, duplicados o falta DETENER';
    END IF;
    INSERT INTO configuracion_invitados(id_vehiculo,habilitada,duracion_s,pulso_ms,actualizado_por,actualizado_utc)
    VALUES(p_unidad,p_habilitada,p_duracion,p_pulso,p_actor,UTC_TIMESTAMP(6))
    ON DUPLICATE KEY UPDATE habilitada=p_habilitada,duracion_s=p_duracion,pulso_ms=p_pulso,
        actualizado_por=p_actor,actualizado_utc=UTC_TIMESTAMP(6);
    DELETE FROM comandos_invitado WHERE id_vehiculo=p_unidad;
    INSERT INTO comandos_invitado(id_vehiculo,id_comando)
    SELECT p_unidad,id_comando FROM JSON_TABLE(p_comandos,'$[*]' COLUMNS(id_comando INT PATH '$')) j;
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
    VALUES(p_actor,'CONFIGURAR_INVITADOS','vehiculo',CAST(p_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
    SELECT p_unidad AS id_vehiculo;
END$$

CREATE PROCEDURE sp_invitado_reservar(IN p_unidad INT, IN p_token_hash BINARY(32))
SQL SECURITY DEFINER
BEGIN
    DECLARE v_id INT DEFAULT NULL;
    DECLARE v_modelo INT;
    DECLARE v_activo INT;
    DECLARE v_estado VARCHAR(20);
    DECLARE v_duracion INT DEFAULT NULL;
    DECLARE v_modelo_publicado INT DEFAULT NULL;
    DECLARE v_sesion BIGINT;
    DECLARE v_inicio DATETIME(6);
    DECLARE v_expira DATETIME(6);
    SELECT id_vehiculo,id_modelo,activo,estado_comercial INTO v_id,v_modelo,v_activo,v_estado
    FROM vehiculos WHERE id_vehiculo=p_unidad FOR UPDATE;
    SELECT id_modelo INTO v_modelo_publicado FROM modelos
    WHERE id_modelo=v_modelo AND activo=1 AND publico=1 FOR UPDATE;
    IF v_id IS NULL OR v_activo<>1 OR v_estado<>'EXHIBICION'
       OR v_modelo_publicado IS NULL
       OR EXISTS(SELECT 1 FROM asignaciones WHERE id_vehiculo=p_unidad AND fin_utc IS NULL) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unidad no disponible para invitados';
    END IF;
    IF EXISTS(SELECT 1 FROM reservas_control WHERE id_vehiculo=p_unidad) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unidad ocupada o pendiente de detencion';
    END IF;
    SELECT duracion_s INTO v_duracion FROM configuracion_invitados
    WHERE id_vehiculo=p_unidad AND habilitada=1 FOR UPDATE;
    IF v_duracion IS NULL OR p_token_hash IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Prueba no habilitada';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM comandos_invitado ci JOIN comandos c ON c.id_comando=ci.id_comando
        WHERE ci.id_vehiculo=p_unidad AND c.id_vehiculo=p_unidad AND c.activo=1 AND c.nombre='DETENER') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='DETENER no esta disponible';
    END IF;
    SET v_inicio=UTC_TIMESTAMP(6);
    SET v_expira=TIMESTAMPADD(SECOND,v_duracion,v_inicio);
    INSERT INTO sesiones_invitado(id_vehiculo,token_hash,inicio_utc,expira_utc)
    VALUES(p_unidad,p_token_hash,v_inicio,v_expira);
    SET v_sesion=LAST_INSERT_ID();
    INSERT INTO reservas_control(id_vehiculo,id_sesion_invitado,creada_utc)
    VALUES(p_unidad,v_sesion,v_inicio);
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
    VALUES(NULL,'RESERVAR_INVITADO','vehiculo',CAST(p_unidad AS CHAR),'ACEPTADO',v_inicio,
           JSON_OBJECT('id_sesion_invitado',v_sesion,'duracion_s',v_duracion));
    SELECT v_sesion AS id_sesion_invitado,p_unidad AS id_vehiculo,v_expira AS expira_utc;
END$$

CREATE PROCEDURE sp_invitado_obtener(IN p_token_hash BINARY(32))
SQL SECURITY DEFINER
BEGIN
    SELECT s.id_sesion_invitado,s.id_vehiculo,s.expira_utc,cfg.pulso_ms,
        TIMESTAMPDIFF(SECOND,UTC_TIMESTAMP(6),s.expira_utc) AS segundos_restantes
    FROM sesiones_invitado s
    JOIN reservas_control r ON r.id_sesion_invitado=s.id_sesion_invitado AND r.id_vehiculo=s.id_vehiculo
    JOIN configuracion_invitados cfg ON cfg.id_vehiculo=s.id_vehiculo AND cfg.habilitada=1
    JOIN vehiculos v ON v.id_vehiculo=s.id_vehiculo AND v.activo=1 AND v.estado_comercial='EXHIBICION'
    JOIN modelos m ON m.id_modelo=v.id_modelo AND m.activo=1 AND m.publico=1
    WHERE s.token_hash=p_token_hash AND s.fin_utc IS NULL AND s.expira_utc>UTC_TIMESTAMP(6) AND r.estado='ACTIVA'
    AND EXISTS(SELECT 1 FROM comandos_invitado ci JOIN comandos c ON c.id_comando=ci.id_comando
        WHERE ci.id_vehiculo=s.id_vehiculo AND c.id_vehiculo=s.id_vehiculo AND c.nombre='DETENER' AND c.activo=1)
    AND NOT EXISTS(SELECT 1 FROM asignaciones a WHERE a.id_vehiculo=s.id_vehiculo AND a.fin_utc IS NULL);
END$$

CREATE PROCEDURE sp_invitado_comandos(IN p_token_hash BINARY(32))
SQL SECURITY DEFINER
BEGIN
    SELECT c.id_comando,c.id_vehiculo,c.nombre,c.codigo,c.descripcion,c.activo
    FROM sesiones_invitado s
    JOIN reservas_control r ON r.id_sesion_invitado=s.id_sesion_invitado AND r.id_vehiculo=s.id_vehiculo AND r.estado='ACTIVA'
    JOIN configuracion_invitados cfg ON cfg.id_vehiculo=s.id_vehiculo AND cfg.habilitada=1
    JOIN comandos_invitado ci ON ci.id_vehiculo=s.id_vehiculo
    JOIN comandos c ON c.id_comando=ci.id_comando AND c.id_vehiculo=s.id_vehiculo AND c.activo=1
    JOIN vehiculos v ON v.id_vehiculo=s.id_vehiculo AND v.activo=1 AND v.estado_comercial='EXHIBICION'
    JOIN modelos m ON m.id_modelo=v.id_modelo AND m.activo=1 AND m.publico=1
    WHERE s.token_hash=p_token_hash AND s.fin_utc IS NULL AND s.expira_utc>UTC_TIMESTAMP(6)
    AND c.nombre IN ('ADELANTE','ATRAS','GIRAR_IZQUIERDA','GIRAR_DERECHA',
        'SUBIR_HORQUILLA','BAJAR_HORQUILLA','LUCES','SONIDO','VELOCIDAD','DETENER')
    AND NOT EXISTS(SELECT 1 FROM asignaciones a WHERE a.id_vehiculo=s.id_vehiculo AND a.fin_utc IS NULL)
    ORDER BY c.codigo;
END$$

CREATE PROCEDURE sp_invitado_cerrar(IN p_sesion BIGINT, IN p_motivo VARCHAR(20))
SQL SECURITY DEFINER
BEGIN
    DECLARE v_unidad INT DEFAULT NULL;
    DECLARE v_lock INT;
    DECLARE v_fin DATETIME(6);
    SELECT id_vehiculo INTO v_unidad FROM sesiones_invitado WHERE id_sesion_invitado=p_sesion;
    IF v_unidad IS NULL OR p_motivo IS NULL
       OR p_motivo NOT IN ('CANCELADA','EXPIRADA','DESCONECTADA','REINICIO','REVOCADA') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Sesion o motivo de cierre invalido';
    END IF;
    SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=v_unidad FOR UPDATE;
    SELECT fin_utc INTO v_fin FROM sesiones_invitado WHERE id_sesion_invitado=p_sesion FOR UPDATE;
    IF v_fin IS NULL THEN
        UPDATE sesiones_invitado SET fin_utc=UTC_TIMESTAMP(6),motivo_fin=p_motivo WHERE id_sesion_invitado=p_sesion;
        UPDATE reservas_control SET estado='DETENIENDO' WHERE id_sesion_invitado=p_sesion;
        INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
        VALUES(NULL,'CERRAR_INVITADO','vehiculo',CAST(v_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),
               JSON_OBJECT('id_sesion_invitado',p_sesion,'motivo',p_motivo));
    END IF;
    SELECT v_unidad AS id_vehiculo,p_sesion AS id_sesion_invitado;
END$$

CREATE PROCEDURE sp_invitado_liberar(IN p_sesion BIGINT)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_unidad INT DEFAULT NULL;
    DECLARE v_lock INT;
    SELECT id_vehiculo INTO v_unidad FROM sesiones_invitado WHERE id_sesion_invitado=p_sesion;
    IF v_unidad IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Sesion inexistente';
    END IF;
    SELECT id_vehiculo INTO v_lock FROM vehiculos WHERE id_vehiculo=v_unidad FOR UPDATE;
    IF NOT EXISTS(SELECT 1 FROM reservas_control r JOIN sesiones_invitado s
        ON s.id_sesion_invitado=r.id_sesion_invitado
        WHERE r.id_sesion_invitado=p_sesion AND r.estado='DETENIENDO' AND s.fin_utc IS NOT NULL) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Se requiere cierre y detencion antes de liberar';
    END IF;
    -- Sólo el servicio de cierre debe llamarla después de procesar DETENER.
    -- No equivale a confirmación física del hardware.
    DELETE FROM reservas_control WHERE id_sesion_invitado=p_sesion;
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
    VALUES(NULL,'LIBERAR_INVITADO','vehiculo',CAST(v_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6),
           JSON_OBJECT('id_sesion_invitado',p_sesion));
    SELECT v_unidad AS id_vehiculo;
END$$

CREATE PROCEDURE sp_invitado_pendientes()
SQL SECURITY DEFINER
BEGIN
    SELECT s.id_sesion_invitado,s.id_vehiculo,r.estado,s.expira_utc
    FROM reservas_control r JOIN sesiones_invitado s ON s.id_sesion_invitado=r.id_sesion_invitado
    LEFT JOIN configuracion_invitados cfg ON cfg.id_vehiculo=s.id_vehiculo
    JOIN vehiculos v ON v.id_vehiculo=s.id_vehiculo
    LEFT JOIN modelos m ON m.id_modelo=v.id_modelo
    WHERE r.estado='DETENIENDO' OR s.expira_utc<=UTC_TIMESTAMP(6) OR s.fin_utc IS NOT NULL
        OR cfg.id_vehiculo IS NULL OR cfg.habilitada=0 OR v.activo=0 OR v.estado_comercial<>'EXHIBICION'
        OR m.id_modelo IS NULL OR m.activo=0 OR m.publico=0
        OR NOT EXISTS(SELECT 1 FROM comandos_invitado ci JOIN comandos c ON c.id_comando=ci.id_comando
            WHERE ci.id_vehiculo=s.id_vehiculo AND c.id_vehiculo=s.id_vehiculo AND c.nombre='DETENER' AND c.activo=1)
        OR EXISTS(SELECT 1 FROM asignaciones a WHERE a.id_vehiculo=v.id_vehiculo AND a.fin_utc IS NULL);
END$$

-- Las rutas comerciales anteriores tampoco pueden alterar una unidad reservada.
CREATE TRIGGER tr_reserva_vehiculo_update BEFORE UPDATE ON vehiculos FOR EACH ROW
BEGIN
    IF EXISTS(SELECT 1 FROM reservas_control WHERE id_vehiculo=OLD.id_vehiculo) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Finaliza la reserva antes de editar la unidad';
    END IF;
END$$

CREATE TRIGGER tr_reserva_comando_update BEFORE UPDATE ON comandos FOR EACH ROW
BEGIN
    IF EXISTS(SELECT 1 FROM reservas_control WHERE id_vehiculo IN (OLD.id_vehiculo,NEW.id_vehiculo)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Finaliza la reserva antes de editar sus comandos';
    END IF;
END$$

CREATE TRIGGER tr_reserva_asignacion_insert BEFORE INSERT ON asignaciones FOR EACH ROW
BEGIN
    IF EXISTS(SELECT 1 FROM reservas_control WHERE id_vehiculo=NEW.id_vehiculo) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Finaliza la reserva antes de asignar la unidad';
    END IF;
END$$

CREATE TRIGGER tr_reserva_asignacion_update BEFORE UPDATE ON asignaciones FOR EACH ROW
BEGIN
    IF EXISTS(SELECT 1 FROM reservas_control WHERE id_vehiculo IN (OLD.id_vehiculo,NEW.id_vehiculo)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Finaliza la reserva antes de cambiar su propietario';
    END IF;
END$$

CREATE TRIGGER tr_reserva_modelo_update BEFORE UPDATE ON modelos FOR EACH ROW
BEGIN
    IF (OLD.activo<>NEW.activo OR OLD.publico<>NEW.publico) AND EXISTS(
        SELECT 1 FROM reservas_control r JOIN vehiculos v ON v.id_vehiculo=r.id_vehiculo
        WHERE v.id_modelo=OLD.id_modelo
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Finaliza las reservas antes de retirar el modelo';
    END IF;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('011_reservas_invitados');
