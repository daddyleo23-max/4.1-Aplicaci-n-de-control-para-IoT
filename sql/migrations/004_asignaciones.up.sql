-- Aplicar después de 003 en la copia.
DELIMITER $$
CREATE PROCEDURE sp_admin_configurar_unidad(
    IN p_actor BIGINT, IN p_unidad INT, IN p_modelo INT,
    IN p_identificador VARCHAR(80)
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_activo INT DEFAULT NULL;
    SELECT activo INTO v_activo FROM vehiculos
    WHERE id_vehiculo=p_unidad FOR UPDATE;
    IF v_activo IS NULL OR v_activo=0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unidad inexistente o inactiva';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM modelos WHERE id_modelo=p_modelo AND activo=1) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Modelo inexistente o inactivo';
    END IF;
    IF EXISTS(SELECT 1 FROM asignaciones WHERE id_vehiculo=p_unidad AND fin_utc IS NULL) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Configura el modelo antes de asignar la unidad';
    END IF;
    UPDATE vehiculos SET id_modelo=p_modelo, identificador_unidad=p_identificador,
        estado_comercial='DISPONIBLE'
    WHERE id_vehiculo=p_unidad;
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
    VALUES(p_actor,'CONFIGURAR_UNIDAD','vehiculo',CAST(p_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
    SELECT p_unidad AS id_vehiculo;
END$$

CREATE PROCEDURE sp_admin_asignar_unidad(
    IN p_actor BIGINT, IN p_unidad INT, IN p_comprador BIGINT
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_activo INT DEFAULT NULL;
    DECLARE v_modelo INT DEFAULT NULL;
    DECLARE v_identificador VARCHAR(80);
    DECLARE v_comprador BIGINT DEFAULT NULL;
    DECLARE v_anterior BIGINT DEFAULT NULL;
    SELECT activo,id_modelo,identificador_unidad INTO v_activo,v_modelo,v_identificador
    FROM vehiculos WHERE id_vehiculo=p_unidad FOR UPDATE;
    IF v_activo IS NULL OR v_activo=0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unidad inexistente o inactiva';
    END IF;
    IF v_modelo IS NULL OR v_identificador IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La unidad necesita modelo e identificador';
    END IF;
    SELECT id_usuario INTO v_comprador FROM usuarios
    WHERE id_usuario=p_comprador AND rol='USUARIO' AND activo=1 FOR UPDATE;
    IF v_comprador IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Comprador inexistente o inactivo';
    END IF;
    SELECT id_usuario INTO v_anterior FROM asignaciones
    WHERE id_vehiculo=p_unidad AND fin_utc IS NULL FOR UPDATE;
    IF v_anterior=p_comprador THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='El comprador ya posee la unidad';
    END IF;
    UPDATE asignaciones SET fin_utc=UTC_TIMESTAMP(6)
    WHERE id_vehiculo=p_unidad AND fin_utc IS NULL;
    INSERT INTO asignaciones(id_vehiculo,id_usuario,asignado_por,inicio_utc)
    VALUES(p_unidad,p_comprador,p_actor,UTC_TIMESTAMP(6));
    UPDATE vehiculos SET estado_comercial='ASIGNADO' WHERE id_vehiculo=p_unidad;
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
    VALUES(p_actor,'ASIGNAR_UNIDAD','vehiculo',CAST(p_unidad AS CHAR),
           'ACEPTADO',UTC_TIMESTAMP(6),JSON_OBJECT('anterior',v_anterior,'nuevo',p_comprador));
    SELECT p_unidad AS id_vehiculo,p_comprador AS id_propietario;
END$$

CREATE PROCEDURE sp_usuario_mis_vehiculos(IN p_usuario BIGINT)
SQL SECURITY DEFINER
BEGIN
    SELECT v.id_vehiculo,v.nombre,v.id_modelo,m.nombre AS nombre_modelo,
           v.identificador_unidad,v.estado_comercial
    FROM asignaciones AS a
    JOIN vehiculos AS v ON v.id_vehiculo=a.id_vehiculo
    JOIN usuarios AS u ON u.id_usuario=a.id_usuario
    LEFT JOIN modelos AS m ON m.id_modelo=v.id_modelo
    WHERE a.id_usuario=p_usuario AND a.fin_utc IS NULL
      AND v.activo=1 AND u.activo=1
    ORDER BY v.id_vehiculo;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('004_asignaciones');
