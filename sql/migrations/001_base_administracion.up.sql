-- Primera entrega 4.3. Aplicar inicialmente mediante migrar_copia_rds.py.
-- MySQL 8.4: las operaciones DDL producen commits implícitos.
-- Ante error parcial, revisar los objetos creados antes de repetir.

CREATE TABLE migraciones_iot (
    version VARCHAR(40) NOT NULL PRIMARY KEY,
    aplicada_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE usuarios (
    id_usuario BIGINT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(120) NOT NULL,
    correo VARCHAR(254) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol ENUM('ADMINISTRADOR', 'USUARIO') NOT NULL,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    creado_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_usuario),
    UNIQUE KEY uq_usuario_correo (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE modelos (
    id_modelo INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    descripcion VARCHAR(500) DEFAULT NULL,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    creado_utc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_modelo),
    UNIQUE KEY uq_modelo_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE vehiculos
    ADD COLUMN id_modelo INT DEFAULT NULL,
    ADD COLUMN identificador_unidad VARCHAR(80) DEFAULT NULL,
    ADD COLUMN estado_comercial ENUM(
        'PENDIENTE', 'DISPONIBLE', 'ASIGNADO', 'EXHIBICION', 'INACTIVO'
    ) NOT NULL DEFAULT 'PENDIENTE',
    ADD UNIQUE KEY uq_vehiculo_identificador (identificador_unidad),
    ADD KEY idx_vehiculo_modelo_estado (id_modelo, estado_comercial),
    ADD CONSTRAINT fk_vehiculo_modelo FOREIGN KEY (id_modelo)
        REFERENCES modelos (id_modelo) ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE asignaciones (
    id_asignacion BIGINT NOT NULL AUTO_INCREMENT,
    id_vehiculo INT NOT NULL,
    id_usuario BIGINT NOT NULL,
    asignado_por BIGINT NOT NULL,
    inicio_utc DATETIME(6) NOT NULL,
    fin_utc DATETIME(6) DEFAULT NULL,
    unidad_vigente INT GENERATED ALWAYS AS (
        CASE WHEN fin_utc IS NULL THEN id_vehiculo ELSE NULL END
    ) STORED,
    PRIMARY KEY (id_asignacion),
    UNIQUE KEY uq_asignacion_vigente (unidad_vigente),
    KEY idx_asignacion_usuario (id_usuario, fin_utc),
    KEY idx_asignacion_vehiculo (id_vehiculo, inicio_utc),
    CONSTRAINT fk_asignacion_vehiculo FOREIGN KEY (id_vehiculo)
        REFERENCES vehiculos (id_vehiculo) ON DELETE RESTRICT,
    CONSTRAINT fk_asignacion_usuario FOREIGN KEY (id_usuario)
        REFERENCES usuarios (id_usuario) ON DELETE RESTRICT,
    CONSTRAINT fk_asignacion_actor FOREIGN KEY (asignado_por)
        REFERENCES usuarios (id_usuario) ON DELETE RESTRICT,
    CONSTRAINT ck_asignacion_fechas CHECK (
        fin_utc IS NULL OR fin_utc >= inicio_utc
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Los modelos, identificadores y propietarios se asignarán tras su revisión.
-- La unidad existente queda PENDIENTE de clasificación comercial.
INSERT INTO migraciones_iot (version) VALUES ('001_base_administracion');
