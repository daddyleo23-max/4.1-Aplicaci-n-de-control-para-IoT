-- Aplicar en la copia después de 001 y 002.
DELIMITER $$
CREATE PROCEDURE sp_admin_resumen()
SQL SECURITY DEFINER
BEGIN
    SELECT
        (SELECT COUNT(*) FROM modelos WHERE activo=1) AS modelos_activos,
        (SELECT COUNT(*) FROM vehiculos WHERE activo=1) AS unidades_activas,
        (SELECT COUNT(*) FROM usuarios WHERE rol='USUARIO' AND activo=1) AS clientes_activos,
        (SELECT COUNT(*) FROM asignaciones WHERE fin_utc IS NULL) AS unidades_asignadas,
        (SELECT COUNT(*) FROM vehiculos WHERE activo=1 AND estado_comercial='EXHIBICION') AS unidades_exhibicion;
END$$

CREATE PROCEDURE sp_admin_listar_modelos(IN p_limite INT, IN p_offset INT)
SQL SECURITY DEFINER
BEGIN
    SELECT id_modelo,nombre,descripcion,activo,creado_utc
    FROM modelos ORDER BY id_modelo DESC LIMIT p_limite OFFSET p_offset;
END$$

CREATE PROCEDURE sp_admin_crear_modelo(
    IN p_actor BIGINT, IN p_nombre VARCHAR(100), IN p_descripcion VARCHAR(500)
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_id INT;
    INSERT INTO modelos(nombre,descripcion) VALUES(p_nombre,p_descripcion);
    SET v_id=LAST_INSERT_ID();
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
    VALUES(p_actor,'CREAR_MODELO','modelo',CAST(v_id AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
    SELECT v_id AS id_modelo;
END$$

CREATE PROCEDURE sp_admin_listar_clientes(IN p_limite INT, IN p_offset INT)
SQL SECURITY DEFINER
BEGIN
    SELECT id_usuario,nombre,correo,activo,creado_utc
    FROM usuarios WHERE rol='USUARIO'
    ORDER BY id_usuario DESC LIMIT p_limite OFFSET p_offset;
END$$

CREATE PROCEDURE sp_admin_crear_cliente(
    IN p_actor BIGINT, IN p_nombre VARCHAR(120), IN p_correo VARCHAR(254),
    IN p_password_hash VARCHAR(255)
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_id BIGINT;
    INSERT INTO usuarios(nombre,correo,password_hash,rol)
    VALUES(p_nombre,p_correo,p_password_hash,'USUARIO');
    SET v_id=LAST_INSERT_ID();
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
    VALUES(p_actor,'CREAR_CLIENTE','usuario',CAST(v_id AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
    SELECT v_id AS id_usuario;
END$$

CREATE PROCEDURE sp_admin_listar_unidades(IN p_limite INT, IN p_offset INT)
SQL SECURITY DEFINER
BEGIN
    SELECT v.id_vehiculo,v.nombre,v.id_modelo,m.nombre AS nombre_modelo,
           v.identificador_unidad,v.estado_comercial,v.activo,
           a.id_usuario AS id_propietario,u.nombre AS propietario
    FROM vehiculos AS v
    LEFT JOIN modelos AS m ON m.id_modelo=v.id_modelo
    LEFT JOIN asignaciones AS a ON a.id_vehiculo=v.id_vehiculo AND a.fin_utc IS NULL
    LEFT JOIN usuarios AS u ON u.id_usuario=a.id_usuario
    ORDER BY v.id_vehiculo DESC LIMIT p_limite OFFSET p_offset;
END$$
DELIMITER ;

INSERT INTO migraciones_iot(version) VALUES('003_gestion_comercial');
