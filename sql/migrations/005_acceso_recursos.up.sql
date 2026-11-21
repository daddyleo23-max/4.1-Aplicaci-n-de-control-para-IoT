-- Contexto de autorización de recursos REST y WSS. Aplicar después de 004.
DELIMITER $$
CREATE PROCEDURE sp_acceso_recurso(IN p_tipo VARCHAR(20), IN p_id BIGINT)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_unidad INT DEFAULT NULL;
    IF p_tipo='vehiculo' THEN
        SET v_unidad=p_id;
    ELSEIF p_tipo='comando' THEN
        SELECT id_vehiculo INTO v_unidad FROM comandos WHERE id_comando=p_id;
    ELSEIF p_tipo='demo' THEN
        SELECT id_vehiculo INTO v_unidad FROM demos WHERE id_demo=p_id;
    ELSEIF p_tipo='paso' THEN
        SELECT d.id_vehiculo INTO v_unidad
        FROM demo_movimientos AS dm JOIN demos AS d ON d.id_demo=dm.id_demo
        WHERE dm.id_demo_movimiento=p_id;
    END IF;
    SELECT v.id_vehiculo,v.activo,v.estado_comercial,a.id_usuario AS id_propietario
    FROM vehiculos AS v
    LEFT JOIN asignaciones AS a ON a.id_vehiculo=v.id_vehiculo AND a.fin_utc IS NULL
    WHERE v.id_vehiculo=v_unidad;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('005_acceso_recursos');
