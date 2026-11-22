-- Capacidades por modelo derivadas del catálogo existente. Primero en copia.
-- El ejecutor comprueba ambigüedades antes del DDL. No cambia IDs ni comandos.
CREATE TABLE capacidades_modelo (
 id_capacidad BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 id_modelo INT NOT NULL,
 nombre VARCHAR(60) NOT NULL,
 codigo INT NOT NULL,
 descripcion VARCHAR(255) NOT NULL DEFAULT '',
 activo TINYINT(1) NOT NULL DEFAULT 1,
 UNIQUE KEY uq_capacidad_codigo(id_modelo,codigo),
 UNIQUE KEY uq_capacidad_nombre(id_modelo,nombre),
 FOREIGN KEY(id_modelo) REFERENCES modelos(id_modelo) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
INSERT INTO capacidades_modelo(id_modelo,nombre,codigo,descripcion,activo)
 SELECT v.id_modelo,MIN(c.nombre),c.codigo,COALESCE(MIN(c.descripcion),''),MAX(c.activo)
 FROM comandos c JOIN vehiculos v ON v.id_vehiculo=c.id_vehiculo
 WHERE v.id_modelo IS NOT NULL GROUP BY v.id_modelo,c.codigo;
DELIMITER $$
CREATE PROCEDURE sp_capacidad_listar(IN p_modelo INT)
SQL SECURITY DEFINER
BEGIN
 SELECT id_capacidad,id_modelo,nombre,codigo,descripcion,activo FROM capacidades_modelo
 WHERE id_modelo=p_modelo ORDER BY codigo,id_capacidad;
END$$
CREATE PROCEDURE sp_capacidad_guardar(IN p_actor BIGINT, IN p_modelo INT, IN p_capacidad BIGINT,
 IN p_nombre VARCHAR(60), IN p_codigo INT, IN p_descripcion VARCHAR(255), IN p_activo BOOLEAN)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_modelo INT DEFAULT NULL;
 DECLARE v_capacidad BIGINT DEFAULT NULL;
 DECLARE v_nombre VARCHAR(60);
 DECLARE v_codigo INT;
 SELECT id_modelo INTO v_modelo FROM modelos WHERE id_modelo=p_modelo AND activo=1 FOR UPDATE;
 IF p_activo IS NULL OR p_activo NOT IN (0,1) OR v_modelo IS NULL OR p_codigo IS NULL OR p_codigo NOT BETWEEN 1 AND 65535 OR p_nombre IS NULL OR LENGTH(TRIM(p_nombre))=0 THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Modelo o capacidad no validos'; END IF;
 IF EXISTS(SELECT 1 FROM reservas_control r JOIN vehiculos v ON v.id_vehiculo=r.id_vehiculo WHERE v.id_modelo=p_modelo) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Finaliza las reservas del modelo antes de editar sus capacidades'; END IF;
 IF p_capacidad IS NOT NULL THEN
 SELECT id_capacidad,nombre,codigo INTO v_capacidad,v_nombre,v_codigo FROM capacidades_modelo
 WHERE id_capacidad=p_capacidad AND id_modelo=p_modelo FOR UPDATE;
 IF v_capacidad IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Capacidad de otro modelo o inexistente'; END IF;
 IF (v_nombre<>p_nombre OR v_codigo<>p_codigo) AND EXISTS(
 SELECT 1 FROM comandos c JOIN vehiculos v ON v.id_vehiculo=c.id_vehiculo
 WHERE v.id_modelo=p_modelo AND c.nombre COLLATE utf8mb4_unicode_ci=v_nombre COLLATE utf8mb4_unicode_ci AND c.codigo=v_codigo) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Una capacidad usada conserva nombre y codigo'; END IF;
 END IF;
 -- Tampoco permitir que una capacidad nueva deshabilitada contradiga comandos activos existentes.
 IF p_activo=0 AND EXISTS(SELECT 1 FROM comandos c JOIN vehiculos v ON v.id_vehiculo=c.id_vehiculo
 WHERE v.id_modelo=p_modelo AND c.nombre COLLATE utf8mb4_unicode_ci=p_nombre COLLATE utf8mb4_unicode_ci AND c.codigo=p_codigo AND c.activo=1) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Desactiva primero los comandos de unidad que usan esta capacidad'; END IF;
 IF p_capacidad IS NULL THEN
 INSERT INTO capacidades_modelo(id_modelo,nombre,codigo,descripcion,activo) VALUES(p_modelo,p_nombre,p_codigo,p_descripcion,p_activo);
 SET v_capacidad=LAST_INSERT_ID();
 ELSE UPDATE capacidades_modelo SET nombre=p_nombre,codigo=p_codigo,descripcion=p_descripcion,activo=p_activo WHERE id_capacidad=v_capacidad;
 END IF;
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
 VALUES(p_actor,'GUARDAR_CAPACIDAD','modelo',CAST(p_modelo AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
 SELECT v_capacidad AS id_capacidad;
END$$
CREATE PROCEDURE sp_capacidad_comandos_unidad(IN p_unidad INT)
SQL SECURITY DEFINER
BEGIN
 SELECT c.id_comando,c.id_vehiculo,c.nombre,c.codigo,c.descripcion,c.activo,k.id_capacidad,
 (k.id_capacidad IS NOT NULL AND k.activo=1) AS compatible
 FROM comandos c JOIN vehiculos v ON v.id_vehiculo=c.id_vehiculo
 LEFT JOIN capacidades_modelo k ON k.id_modelo=v.id_modelo AND k.codigo=c.codigo AND k.nombre COLLATE utf8mb4_unicode_ci=c.nombre COLLATE utf8mb4_unicode_ci
 WHERE c.id_vehiculo=p_unidad ORDER BY c.codigo,c.id_comando;
END$$
CREATE PROCEDURE sp_capacidad_comando_guardar(IN p_actor BIGINT, IN p_unidad INT, IN p_comando INT,
 IN p_capacidad BIGINT, IN p_descripcion VARCHAR(255), IN p_activo BOOLEAN)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_unidad INT DEFAULT NULL;
 DECLARE v_modelo INT;
 DECLARE v_activa TINYINT;
 DECLARE v_nombre VARCHAR(60) DEFAULT NULL;
 DECLARE v_codigo INT;
 DECLARE v_habilitada TINYINT;
 DECLARE v_comando INT DEFAULT NULL;
 DECLARE v_anterior VARCHAR(60);
 DECLARE v_codigo_anterior INT;
 SELECT id_vehiculo,id_modelo,activo INTO v_unidad,v_modelo,v_activa FROM vehiculos WHERE id_vehiculo=p_unidad FOR UPDATE;
 IF p_activo IS NULL OR p_activo NOT IN (0,1) OR v_unidad IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unidad inexistente'; END IF;
 CALL sp_reserva_exigir_libre(p_unidad);
 SELECT nombre,codigo,activo INTO v_nombre,v_codigo,v_habilitada FROM capacidades_modelo
 WHERE id_capacidad=p_capacidad AND id_modelo=v_modelo FOR UPDATE;
 IF v_nombre IS NULL OR (p_activo=1 AND v_habilitada=0) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La capacidad no pertenece al modelo o esta deshabilitada'; END IF;
 IF p_comando IS NOT NULL THEN
 SELECT id_comando,nombre,codigo INTO v_comando,v_anterior,v_codigo_anterior FROM comandos
 WHERE id_comando=p_comando AND id_vehiculo=p_unidad FOR UPDATE;
 IF v_comando IS NULL OR v_anterior<>v_nombre OR v_codigo_anterior<>v_codigo THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='El comando conserva su unidad, nombre y codigo'; END IF;
 END IF;
 IF v_nombre='DETENER' AND p_activo=0 AND v_activa=1 THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Una unidad activa debe conservar DETENER habilitado'; END IF;
 IF p_comando IS NULL THEN
 INSERT INTO comandos(id_vehiculo,nombre,codigo,descripcion,activo) VALUES(p_unidad,v_nombre,v_codigo,p_descripcion,p_activo);
 SET v_comando=LAST_INSERT_ID();
 ELSE UPDATE comandos SET descripcion=p_descripcion,activo=p_activo WHERE id_comando=v_comando;
 END IF;
 INSERT INTO auditoria(id_actor,accion,tipo_recurso,id_recurso,resultado,fecha_utc)
 VALUES(p_actor,'GUARDAR_COMANDO_UNIDAD','comando',CAST(v_comando AS CHAR),'ACEPTADO',UTC_TIMESTAMP(6));
 SELECT v_comando AS id_comando;
END$$
CREATE PROCEDURE sp_capacidad_exigir(IN p_unidad INT, IN p_comando INT)
SQL SECURITY DEFINER
BEGIN
 IF NOT EXISTS(SELECT 1 FROM comandos c JOIN vehiculos v ON v.id_vehiculo=c.id_vehiculo AND v.activo=1
 JOIN modelos m ON m.id_modelo=v.id_modelo AND m.activo=1
 JOIN capacidades_modelo k ON k.id_modelo=v.id_modelo AND k.nombre COLLATE utf8mb4_unicode_ci=c.nombre COLLATE utf8mb4_unicode_ci AND k.codigo=c.codigo AND k.activo=1
 WHERE c.id_vehiculo=p_unidad AND c.id_comando=p_comando AND c.activo=1) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='El comando no esta habilitado para esta unidad y modelo'; END IF;
END$$
DELIMITER ;
INSERT INTO migraciones_iot(version) VALUES('018_capacidades_modelo');
