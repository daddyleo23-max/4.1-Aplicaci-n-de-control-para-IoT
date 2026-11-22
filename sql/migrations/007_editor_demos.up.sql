-- Propiedad y guardado completo de demos. Requiere 006.
ALTER TABLE demos
    ADD COLUMN id_propietario BIGINT DEFAULT NULL,
    ADD COLUMN tipo ENUM('EMPRESA','PRIVADA') NOT NULL DEFAULT 'EMPRESA',
    ADD COLUMN revision INT UNSIGNED NOT NULL DEFAULT 1,
    ADD KEY idx_demo_propietario (id_propietario, activo),
    ADD CONSTRAINT fk_demo_propietario FOREIGN KEY (id_propietario)
        REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
    ADD CONSTRAINT ck_demo_propiedad CHECK (
        (tipo='EMPRESA' AND id_propietario IS NULL) OR
        (tipo='PRIVADA' AND id_propietario IS NOT NULL)
    );

DELIMITER $$
CREATE PROCEDURE sp_editor_listar_demos(IN p_actor BIGINT, IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
    SELECT d.* FROM demos AS d
    JOIN vehiculos AS v ON v.id_vehiculo=d.id_vehiculo
    JOIN usuarios AS u ON u.id_usuario=p_actor AND u.activo=1
    LEFT JOIN asignaciones AS a ON a.id_vehiculo=v.id_vehiculo AND a.fin_utc IS NULL
    WHERE v.id_vehiculo=p_unidad AND v.activo=1
      AND ((u.rol='USUARIO' AND a.id_usuario=p_actor)
        OR (u.rol='ADMINISTRADOR' AND a.id_usuario IS NULL))
      AND (d.tipo='EMPRESA' OR d.id_propietario=p_actor)
    ORDER BY d.id_demo DESC;
END$$

CREATE PROCEDURE sp_editor_detalle_demo(IN p_actor BIGINT, IN p_demo INT)
SQL SECURITY DEFINER
BEGIN
    SELECT d.* FROM demos AS d
    JOIN vehiculos AS v ON v.id_vehiculo=d.id_vehiculo
    JOIN usuarios AS u ON u.id_usuario=p_actor AND u.activo=1
    LEFT JOIN asignaciones AS a ON a.id_vehiculo=v.id_vehiculo AND a.fin_utc IS NULL
    WHERE d.id_demo=p_demo AND v.activo=1
      AND ((u.rol='USUARIO' AND a.id_usuario=p_actor)
        OR (u.rol='ADMINISTRADOR' AND a.id_usuario IS NULL))
      AND (d.tipo='EMPRESA' OR d.id_propietario=p_actor);
END$$

CREATE PROCEDURE sp_editor_guardar_demo(
    IN p_actor BIGINT, IN p_demo INT, IN p_unidad INT,
    IN p_revision INT, IN p_nombre VARCHAR(80), IN p_descripcion VARCHAR(255),
    IN p_activo BOOLEAN, IN p_pasos JSON
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_rol VARCHAR(20) DEFAULT NULL;
    DECLARE v_activo INT DEFAULT NULL;
    DECLARE v_dueno BIGINT DEFAULT NULL;
    DECLARE v_demo INT DEFAULT NULL;
    DECLARE v_demo_dueno BIGINT DEFAULT NULL;
    DECLARE v_demo_unidad INT DEFAULT NULL;
    DECLARE v_tipo VARCHAR(10);
    DECLARE v_revision INT;
    DECLARE v_total BIGINT;
    DECLARE v_cantidad INT;
    SELECT rol INTO v_rol FROM usuarios WHERE id_usuario=p_actor AND activo=1;
    SELECT activo INTO v_activo FROM vehiculos WHERE id_vehiculo=p_unidad FOR UPDATE;
    SELECT id_usuario INTO v_dueno FROM asignaciones
    WHERE id_vehiculo=p_unidad AND fin_utc IS NULL FOR UPDATE;
    IF v_rol IS NULL OR v_activo IS NULL OR v_activo=0
       OR NOT ((v_rol='USUARIO' AND v_dueno IS NOT NULL AND v_dueno=p_actor)
           OR (v_rol='ADMINISTRADOR' AND v_dueno IS NULL)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Sin acceso operativo a la unidad';
    END IF;
    IF p_nombre IS NULL OR CHAR_LENGTH(TRIM(p_nombre))=0
       OR p_pasos IS NULL OR JSON_TYPE(p_pasos)<>'ARRAY' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Nombre o secuencia inválidos';
    END IF;
    SELECT COUNT(*), COALESCE(SUM(j.duracion_ms+j.pausa_ms),0)
    INTO v_cantidad,v_total
    FROM JSON_TABLE(p_pasos,'$[*]' COLUMNS(
        id_comando INT PATH '$.id_comando' ERROR ON EMPTY ERROR ON ERROR,
        duracion_ms INT PATH '$.duracion_ms' ERROR ON EMPTY ERROR ON ERROR,
        pausa_ms INT PATH '$.pausa_ms' ERROR ON EMPTY ERROR ON ERROR
    )) AS j;
    IF v_cantidad<1 OR v_cantidad>100 OR v_total>120000 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Secuencia fuera de límites';
    END IF;
    IF EXISTS(
        SELECT 1 FROM JSON_TABLE(p_pasos,'$[*]' COLUMNS(
            id_comando INT PATH '$.id_comando',
            duracion_ms INT PATH '$.duracion_ms',
            pausa_ms INT PATH '$.pausa_ms'
        )) AS j
        LEFT JOIN comandos AS c ON c.id_comando=j.id_comando
        WHERE c.id_comando IS NULL OR c.id_vehiculo<>p_unidad OR c.activo=0
          OR UPPER(c.nombre) IN ('DEMO','AUTO DEMO','AUTO_DEMO')
          OR j.duracion_ms IS NULL OR j.pausa_ms IS NULL
          OR j.duracion_ms<1 OR j.duracion_ms>10000
          OR j.pausa_ms<0 OR j.pausa_ms>5000
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Paso incompatible o duración inválida';
    END IF;
    IF p_demo IS NULL THEN
        SET v_tipo=IF(v_rol='ADMINISTRADOR','EMPRESA','PRIVADA');
        INSERT INTO demos(id_vehiculo,nombre,descripcion,activo,id_propietario,tipo)
        VALUES(p_unidad,TRIM(p_nombre),p_descripcion,p_activo,
               IF(v_tipo='PRIVADA',p_actor,NULL),v_tipo);
        SET v_demo=LAST_INSERT_ID();
        SET v_revision=1;
    ELSE
        SELECT id_demo,id_vehiculo,id_propietario,tipo,revision
        INTO v_demo,v_demo_unidad,v_demo_dueno,v_tipo,v_revision
        FROM demos WHERE id_demo=p_demo FOR UPDATE;
        IF v_demo IS NULL OR v_demo_unidad<>p_unidad
           OR (v_tipo='EMPRESA' AND v_rol<>'ADMINISTRADOR')
           OR (v_tipo='PRIVADA' AND (v_demo_dueno IS NULL OR v_demo_dueno<>p_actor)) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Sin permiso para editar esta demo';
        END IF;
        IF p_revision IS NULL OR p_revision<>v_revision THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La demo cambió; vuelve a cargarla';
        END IF;
        UPDATE demos SET nombre=TRIM(p_nombre),descripcion=p_descripcion,
            activo=p_activo,revision=revision+1 WHERE id_demo=v_demo;
        SET v_revision=v_revision+1;
        DELETE FROM demo_movimientos WHERE id_demo=v_demo;
    END IF;
    INSERT INTO demo_movimientos(id_demo,id_comando,orden,duracion_ms,pausa_ms)
    SELECT v_demo,j.orden,j.id_comando,j.duracion_ms,j.pausa_ms
    FROM JSON_TABLE(p_pasos,'$[*]' COLUMNS(
        orden FOR ORDINALITY,
        id_comando INT PATH '$.id_comando',
        duracion_ms INT PATH '$.duracion_ms',
        pausa_ms INT PATH '$.pausa_ms'
    )) AS j;
    INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
    VALUES(p_actor,'GUARDAR_DEMO','demo',CAST(v_demo AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
    SELECT v_demo AS id_demo,v_revision AS revision,v_total AS duracion_total_ms;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('007_editor_demos');
