-- Aplicar después de 009, primero en la copia. DDL con commit implícito.
-- La publicación es explícita: ningún modelo existente se hace público al migrar.
ALTER TABLE modelos ADD COLUMN publico TINYINT(1) NOT NULL DEFAULT 0;

DELIMITER $$
CREATE PROCEDURE sp_admin_publicar_modelo(
    IN p_actor BIGINT, IN p_modelo INT, IN p_publico BOOLEAN
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_activo INT DEFAULT NULL;
    SELECT activo INTO v_activo FROM modelos WHERE id_modelo=p_modelo FOR UPDATE;
    IF v_activo IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Modelo inexistente';
    END IF;
    IF p_publico=1 AND v_activo=0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Activa el modelo antes de publicarlo';
    END IF;
    UPDATE modelos SET publico=p_publico WHERE id_modelo=p_modelo;
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
    VALUES(p_actor,'PUBLICAR_MODELO','modelo',CAST(p_modelo AS CHAR),'ACEPTADO',
           UTC_TIMESTAMP(6),JSON_OBJECT('publico',p_publico));
    SELECT p_modelo AS id_modelo,p_publico AS publico;
END$$

DROP PROCEDURE sp_admin_listar_modelos$$
CREATE PROCEDURE sp_admin_listar_modelos(IN p_limite INT, IN p_offset INT)
SQL SECURITY DEFINER
BEGIN
    SELECT id_modelo,nombre,descripcion,activo,publico,creado_utc
    FROM modelos ORDER BY id_modelo DESC LIMIT p_limite OFFSET p_offset;
END$$

CREATE PROCEDURE sp_admin_marcar_exhibicion(
    IN p_actor BIGINT, IN p_unidad INT, IN p_habilitada BOOLEAN
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_activo INT DEFAULT NULL;
    DECLARE v_modelo INT;
    SELECT activo,id_modelo INTO v_activo,v_modelo FROM vehiculos
    WHERE id_vehiculo=p_unidad FOR UPDATE;
    IF v_activo IS NULL OR v_activo=0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unidad inexistente o inactiva';
    END IF;
    IF EXISTS(SELECT 1 FROM asignaciones WHERE id_vehiculo=p_unidad AND fin_utc IS NULL) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Una unidad asignada no puede destinarse a exhibicion';
    END IF;
    IF p_habilitada=1 AND NOT EXISTS(
        SELECT 1 FROM modelos WHERE id_modelo=v_modelo AND activo=1 AND publico=1
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Publica primero un modelo activo para esta unidad';
    END IF;
    UPDATE vehiculos SET estado_comercial=IF(p_habilitada,'EXHIBICION','DISPONIBLE')
    WHERE id_vehiculo=p_unidad;
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc,detalles)
    VALUES(p_actor,'EXHIBICION_UNIDAD','vehiculo',CAST(p_unidad AS CHAR),'ACEPTADO',
           UTC_TIMESTAMP(6),JSON_OBJECT('habilitada',p_habilitada));
    SELECT p_unidad AS id_vehiculo,p_habilitada AS exhibicion;
END$$

CREATE PROCEDURE sp_catalogo_modelos(IN p_limite INT, IN p_offset INT)
SQL SECURITY DEFINER
BEGIN
    SELECT m.id_modelo,m.nombre,COALESCE(m.descripcion,'') AS descripcion,
        (SELECT COUNT(*) FROM vehiculos v
         WHERE v.id_modelo=m.id_modelo AND v.activo=1 AND v.estado_comercial='EXHIBICION'
         AND NOT EXISTS(SELECT 1 FROM asignaciones a
                        WHERE a.id_vehiculo=v.id_vehiculo AND a.fin_utc IS NULL))
        AS unidades_exhibicion
    FROM modelos m WHERE m.activo=1 AND m.publico=1
    ORDER BY m.id_modelo DESC LIMIT p_limite OFFSET p_offset;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('010_catalogo_publico');
