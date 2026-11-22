-- Después de 008, inicialmente en la copia aislada. DDL con commit implícito.
-- Sólo crea/reemplaza rutinas administrativas; no modifica datos existentes.
DELIMITER $$
CREATE PROCEDURE sp_admin_crear_unidad(
    IN p_actor BIGINT, IN p_nombre VARCHAR(80), IN p_modelo INT,
    IN p_identificador VARCHAR(80), IN p_descripcion VARCHAR(255),
    IN p_microcontrolador VARCHAR(50)
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_modelo VARCHAR(100) DEFAULT NULL;
    DECLARE v_id INT;
    SELECT nombre INTO v_modelo FROM modelos WHERE id_modelo=p_modelo AND activo=1 FOR UPDATE;
    IF v_modelo IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Modelo inexistente o inactivo';
    END IF;
    INSERT INTO vehiculos(nombre,modelo,descripcion,microcontrolador,id_modelo,
                          identificador_unidad,estado_comercial,activo)
    VALUES(p_nombre,LEFT(v_modelo,80),p_descripcion,p_microcontrolador,p_modelo,
           p_identificador,'DISPONIBLE',1);
    SET v_id=LAST_INSERT_ID();
    -- Una unidad registrada no hereda comandos ni representa conexión física.
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
    VALUES(p_actor,'CREAR_UNIDAD','vehiculo',CAST(v_id AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
    SELECT v_id AS id_vehiculo;
END$$

CREATE PROCEDURE sp_admin_actualizar_unidad(
    IN p_actor BIGINT, IN p_unidad INT, IN p_nombre VARCHAR(80), IN p_modelo INT,
    IN p_identificador VARCHAR(80), IN p_descripcion VARCHAR(255),
    IN p_microcontrolador VARCHAR(50), IN p_activo BOOLEAN
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_id INT DEFAULT NULL;
    DECLARE v_modelo_actual INT;
    DECLARE v_modelo VARCHAR(100) DEFAULT NULL;
    DECLARE v_estado VARCHAR(20);
    DECLARE v_propietario BIGINT DEFAULT NULL;
    SELECT id_vehiculo,id_modelo,estado_comercial INTO v_id,v_modelo_actual,v_estado
    FROM vehiculos WHERE id_vehiculo=p_unidad FOR UPDATE;
    IF v_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unidad inexistente';
    END IF;
    SELECT nombre INTO v_modelo FROM modelos WHERE id_modelo=p_modelo AND activo=1 FOR UPDATE;
    IF v_modelo IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Modelo inexistente o inactivo';
    END IF;
    SELECT id_usuario INTO v_propietario FROM asignaciones
    WHERE id_vehiculo=p_unidad AND fin_utc IS NULL FOR UPDATE;
    IF v_propietario IS NOT NULL AND (p_activo=0 OR NOT (v_modelo_actual <=> p_modelo)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Una unidad asignada conserva su modelo y estado activo';
    END IF;
    IF NOT (v_modelo_actual <=> p_modelo) AND (
        EXISTS(SELECT 1 FROM comandos WHERE id_vehiculo=p_unidad)
        OR EXISTS(SELECT 1 FROM demos WHERE id_vehiculo=p_unidad)
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Revisa las capacidades antes de cambiar el modelo de una unidad con comandos o demos';
    END IF;
    UPDATE vehiculos SET nombre=p_nombre,modelo=LEFT(v_modelo,80),id_modelo=p_modelo,
        identificador_unidad=p_identificador,descripcion=p_descripcion,
        microcontrolador=p_microcontrolador,activo=p_activo,
        estado_comercial=CASE WHEN p_activo=0 THEN 'INACTIVO'
            WHEN v_propietario IS NOT NULL THEN 'ASIGNADO'
            WHEN v_estado='EXHIBICION' THEN 'EXHIBICION' ELSE 'DISPONIBLE' END
    WHERE id_vehiculo=p_unidad;
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
    VALUES(p_actor,'ACTUALIZAR_UNIDAD','vehiculo',CAST(p_unidad AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
    SELECT p_unidad AS id_vehiculo;
END$$

DROP PROCEDURE sp_admin_listar_unidades$$
CREATE PROCEDURE sp_admin_listar_unidades(IN p_limite INT, IN p_offset INT)
SQL SECURITY DEFINER
BEGIN
    SELECT v.id_vehiculo,v.nombre,v.id_modelo,m.nombre AS nombre_modelo,
           v.identificador_unidad,v.estado_comercial,v.activo,v.descripcion,v.microcontrolador,
           a.id_usuario AS id_propietario,u.nombre AS propietario
    FROM vehiculos AS v
    LEFT JOIN modelos AS m ON m.id_modelo=v.id_modelo
    LEFT JOIN asignaciones AS a ON a.id_vehiculo=v.id_vehiculo AND a.fin_utc IS NULL
    LEFT JOIN usuarios AS u ON u.id_usuario=a.id_usuario
    ORDER BY v.id_vehiculo DESC LIMIT p_limite OFFSET p_offset;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('009_inventario_unidades');
