-- --------------------------------------------------------
-- Host:                         127.0.0.1
-- Server version:               10.4.32-MariaDB - mariadb.org binary distribution
-- Server OS:                    Win64
-- HeidiSQL Version:             12.10.0.7000
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- Dumping database structure for gestor_instalaciones
CREATE DATABASE IF NOT EXISTS `gestor_instalaciones` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci */;
USE `gestor_instalaciones`;

-- Dumping structure for table gestor_instalaciones.instalaciones
CREATE TABLE IF NOT EXISTS `instalaciones` (
  `id_instalacion` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `nombre` varchar(255) NOT NULL,
  `descripcion` text DEFAULT NULL,
  `estado` varchar(50) NOT NULL DEFAULT 'Disponible',
  `imagen_url` text DEFAULT NULL,
  `hora_solicitada` time DEFAULT NULL,
  `codigo_cliente` varchar(50) DEFAULT NULL,
  `solicitud` varchar(255) DEFAULT NULL,
  `tecnico_asignado` varchar(255) DEFAULT NULL,
  `id_instalador` int(11) DEFAULT NULL,
  `nombre_cliente` varchar(255) DEFAULT NULL,
  `telefono_cliente` varchar(20) DEFAULT NULL,
  `referencia` text DEFAULT NULL,
  `ruta_caja_nap` varchar(255) DEFAULT NULL,
  `ubicacion_gps` varchar(255) DEFAULT NULL,
  `descripcion_final` text DEFAULT NULL,
  `ubicacion_gps_final` varchar(255) DEFAULT NULL,
  `foto_adjunta` varchar(255) DEFAULT NULL,
  `numero_serie` varchar(255) DEFAULT NULL,
  `metodo_pago` varchar(50) DEFAULT NULL,
  `numero_transaccion` varchar(255) DEFAULT NULL,
  `fecha_completado` datetime DEFAULT NULL,
  PRIMARY KEY (`id_instalacion`)
) ENGINE=InnoDB AUTO_INCREMENT=35 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Data exporting was unselected.

-- Dumping structure for table gestor_instalaciones.reservas
CREATE TABLE IF NOT EXISTS `reservas` (
  `id_reserva` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `id_instalacion` int(10) unsigned NOT NULL,
  `nombre_cliente` varchar(255) NOT NULL,
  `fecha` date NOT NULL,
  `hora_inicio` time NOT NULL,
  `hora_fin` time NOT NULL,
  `estado` varchar(50) NOT NULL DEFAULT 'Confirmada',
  `id_usuario` int(11) DEFAULT NULL,
  PRIMARY KEY (`id_reserva`),
  KEY `id_instalacion` (`id_instalacion`),
  CONSTRAINT `reservas_ibfk_1` FOREIGN KEY (`id_instalacion`) REFERENCES `instalaciones` (`id_instalacion`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Data exporting was unselected.

-- Dumping structure for table gestor_instalaciones.solicitudes
CREATE TABLE IF NOT EXISTS `solicitudes` (
  ```id_solicitud``` int(10) NOT NULL AUTO_INCREMENT,
  `id_instalacion` int(10) NOT NULL,
  `hora_solicitada` time NOT NULL,
  `estado` varchar(50) NOT NULL DEFAULT '' COMMENT 'Pendiente',
  `codigo_cliente` varchar(50) NOT NULL DEFAULT '',
  `solicitud` varchar(255) NOT NULL DEFAULT '',
  `tecnico_asignado` varchar(255) NOT NULL DEFAULT '',
  `nombre_cliente` varchar(255) NOT NULL DEFAULT '',
  `telefono_cliente` varchar(20) NOT NULL DEFAULT '',
  `referencia` text NOT NULL,
  `ruta_caja_nap` varchar(255) NOT NULL,
  `ubicacion_gps` varchar(50) NOT NULL,
  PRIMARY KEY (```id_solicitud```)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Data exporting was unselected.

-- Dumping structure for table gestor_instalaciones.tareas
CREATE TABLE IF NOT EXISTS `tareas` (
  `id_tarea` int(10) NOT NULL AUTO_INCREMENT,
  `id_instalacion` int(10) unsigned NOT NULL,
  `id_admin` int(10) unsigned NOT NULL,
  `id_usuario_asignado` int(10) unsigned NOT NULL,
  `tipo_tarea` varchar(50) NOT NULL,
  `descripcion` text NOT NULL,
  `fecha_asignacion` date NOT NULL,
  `estado` varchar(50) NOT NULL,
  PRIMARY KEY (`id_tarea`),
  KEY `id_instalacion` (`id_instalacion`),
  KEY `id_admin` (`id_admin`),
  KEY `id_usuario_asignado` (`id_usuario_asignado`),
  CONSTRAINT `fk_tareas_admin` FOREIGN KEY (`id_admin`) REFERENCES `usuarios` (`id_usuario`),
  CONSTRAINT `fk_tareas_instalacion` FOREIGN KEY (`id_instalacion`) REFERENCES `instalaciones` (`id_instalacion`),
  CONSTRAINT `fk_tareas_usuario_asignado` FOREIGN KEY (`id_usuario_asignado`) REFERENCES `usuarios` (`id_usuario`),
  CONSTRAINT `tareas_ibfk_1` FOREIGN KEY (`id_instalacion`) REFERENCES `instalaciones` (`id_instalacion`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Data exporting was unselected.

-- Dumping structure for table gestor_instalaciones.usuarios
CREATE TABLE IF NOT EXISTS `usuarios` (
  `id_usuario` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `nombre` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password` varchar(255) NOT NULL,
  `es_admin` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id_usuario`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Data exporting was unselected.

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
