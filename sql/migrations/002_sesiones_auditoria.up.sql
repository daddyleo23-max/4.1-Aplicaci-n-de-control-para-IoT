-- Propuesta de segunda migración. Requiere 001 validada.
-- Revisar antes de aplicar en la copia. DDL con commits implícitos.

CREATE TABLE sesiones (
    id_sesion BIGINT NOT NULL AUTO_INCREMENT,
    id_usuario BIGINT NOT NULL,
    token_hash BINARY(32) NOT NULL,
    creada_utc DATETIME(6) NOT NULL,
    expira_utc DATETIME(6) NOT NULL,
    revocada_utc DATETIME(6) DEFAULT NULL,
    PRIMARY KEY (id_sesion),
    UNIQUE KEY uq_sesion_token (token_hash),
    KEY idx_sesion_usuario (id_usuario, revocada_utc, expira_utc),
    KEY idx_sesion_expiracion (expira_utc),
    CONSTRAINT fk_sesion_usuario FOREIGN KEY (id_usuario)
        REFERENCES usuarios (id_usuario) ON DELETE RESTRICT,
    CONSTRAINT ck_sesion_expiracion CHECK (expira_utc > creada_utc),
    CONSTRAINT ck_sesion_revocacion CHECK (
        revocada_utc IS NULL OR revocada_utc >= creada_utc
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE auditoria (
    id_auditoria BIGINT NOT NULL AUTO_INCREMENT,
    id_actor BIGINT DEFAULT NULL,
    accion VARCHAR(80) NOT NULL,
    tipo_recurso VARCHAR(60) NOT NULL,
    id_recurso VARCHAR(80) DEFAULT NULL,
    resultado ENUM('ACEPTADO', 'RECHAZADO', 'ERROR') NOT NULL,
    fecha_utc DATETIME(6) NOT NULL,
    detalles JSON DEFAULT NULL,
    PRIMARY KEY (id_auditoria),
    KEY idx_auditoria_actor_fecha (id_actor, fecha_utc),
    KEY idx_auditoria_recurso (tipo_recurso, id_recurso, fecha_utc),
    CONSTRAINT fk_auditoria_actor FOREIGN KEY (id_actor)
        REFERENCES usuarios (id_usuario) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Las rutinas usan los permisos de la cuenta administradora que las crea.
DELIMITER $$
CREATE PROCEDURE sp_auth_buscar_usuario(IN p_correo VARCHAR(254))
SQL SECURITY DEFINER
BEGIN
    SELECT id_usuario, nombre, correo, rol, password_hash, activo
    FROM usuarios WHERE correo = p_correo;
END$$

CREATE PROCEDURE sp_auth_crear_sesion(
    IN p_usuario BIGINT, IN p_hash BINARY(32), IN p_expira DATETIME(6)
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_creadas INT;
    INSERT INTO sesiones(id_usuario, token_hash, creada_utc, expira_utc)
    SELECT id_usuario, p_hash, UTC_TIMESTAMP(6), p_expira
    FROM usuarios WHERE id_usuario = p_usuario AND activo = 1;
    SET v_creadas = ROW_COUNT();
    IF v_creadas = 1 THEN
        INSERT INTO auditoria(id_actor, accion, tipo_recurso, id_recurso,
                              resultado, fecha_utc)
        VALUES(p_usuario, 'LOGIN', 'usuario', CAST(p_usuario AS CHAR),
               'ACEPTADO', UTC_TIMESTAMP(6));
    END IF;
    SELECT v_creadas AS creadas;
END$$

CREATE PROCEDURE sp_auth_obtener_sesion(IN p_hash BINARY(32))
SQL SECURITY DEFINER
BEGIN
    SELECT s.id_sesion, u.id_usuario, u.nombre, u.correo, u.rol
    FROM sesiones AS s JOIN usuarios AS u ON u.id_usuario = s.id_usuario
    WHERE s.token_hash = p_hash AND s.revocada_utc IS NULL
      AND s.expira_utc > UTC_TIMESTAMP(6) AND u.activo = 1;
END$$

CREATE PROCEDURE sp_auth_revocar_sesion(IN p_sesion BIGINT)
SQL SECURITY DEFINER
BEGIN
    UPDATE sesiones SET revocada_utc = UTC_TIMESTAMP(6)
    WHERE id_sesion = p_sesion AND revocada_utc IS NULL;
    IF ROW_COUNT() = 1 THEN
        INSERT INTO auditoria(id_actor, accion, tipo_recurso, id_recurso,
                              resultado, fecha_utc)
        SELECT id_usuario, 'LOGOUT', 'sesion', CAST(id_sesion AS CHAR),
               'ACEPTADO', UTC_TIMESTAMP(6)
        FROM sesiones WHERE id_sesion = p_sesion;
    END IF;
END$$
DELIMITER ;

-- Guardar solo hashes de tokens. Redactar credenciales en auditoría.
INSERT INTO migraciones_iot (version) VALUES ('002_sesiones_auditoria');
