-- Edición comercial y consulta de auditoría. Aplicar después de 005.
DELIMITER $$
CREATE PROCEDURE sp_admin_actualizar_modelo(
    IN p_actor BIGINT, IN p_id INT, IN p_nombre VARCHAR(100),
    IN p_descripcion VARCHAR(500), IN p_activo BOOLEAN
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_id INT DEFAULT NULL;
    SELECT id_modelo INTO v_id FROM modelos WHERE id_modelo=p_id FOR UPDATE;
    IF v_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Modelo inexistente';
    END IF;
    IF p_activo=0 AND EXISTS(
        SELECT 1 FROM vehiculos WHERE id_modelo=p_id AND activo=1
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='El modelo tiene unidades activas';
    END IF;
    UPDATE modelos SET nombre=p_nombre,descripcion=p_descripcion,activo=p_activo
    WHERE id_modelo=p_id;
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
    VALUES(p_actor,'ACTUALIZAR_MODELO','modelo',CAST(p_id AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
    SELECT p_id AS id_modelo;
END$$

CREATE PROCEDURE sp_admin_actualizar_cliente(
    IN p_actor BIGINT, IN p_id BIGINT, IN p_nombre VARCHAR(120),
    IN p_correo VARCHAR(254), IN p_activo BOOLEAN
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_id BIGINT DEFAULT NULL;
    SELECT id_usuario INTO v_id FROM usuarios
    WHERE id_usuario=p_id AND rol='USUARIO' FOR UPDATE;
    IF v_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Comprador inexistente';
    END IF;
    UPDATE usuarios SET nombre=p_nombre,correo=p_correo,activo=p_activo
    WHERE id_usuario=p_id;
    IF p_activo=0 THEN
        UPDATE sesiones SET revocada_utc=UTC_TIMESTAMP(6)
        WHERE id_usuario=p_id AND revocada_utc IS NULL;
    END IF;
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
    VALUES(p_actor,'ACTUALIZAR_CLIENTE','usuario',CAST(p_id AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
    SELECT p_id AS id_usuario;
END$$

CREATE PROCEDURE sp_admin_listar_auditoria(IN p_limite INT, IN p_offset INT)
SQL SECURITY DEFINER
BEGIN
    SELECT id_auditoria,id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles
    FROM auditoria ORDER BY fecha_utc DESC,id_auditoria DESC
    LIMIT p_limite OFFSET p_offset;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('006_edicion_auditoria');
