-- MySQL dump 10.13  Distrib 8.0.45, for Linux (x86_64)
--
-- Host: localhost    Database: billing
-- ------------------------------------------------------
-- Server version	8.0.45-0ubuntu0.24.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `clients`
--

DROP TABLE IF EXISTS `clients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clients` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Название клиента/компании',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_clients_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=153 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Клиенты дата-центра';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `daily_billing`
--

DROP TABLE IF EXISTS `daily_billing`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `daily_billing` (
  `id` int NOT NULL AUTO_INCREMENT,
  `billing_date` date NOT NULL COMMENT 'Дата, за которую произведен расчет',
  `vm_id` int NOT NULL COMMENT 'ID виртуального сервера',
  `client_id` int NOT NULL COMMENT 'ID клиента (денормализация для ускорения запросов)',
  `cpu_cores` int NOT NULL COMMENT 'Количество ядер CPU',
  `ram_gb` int NOT NULL COMMENT 'Объем RAM в ГБ',
  `nvme1_gb` int DEFAULT '0' COMMENT 'NVME диск 1 в ГБ',
  `nvme2_gb` int DEFAULT '0' COMMENT 'NVME диск 2 в ГБ',
  `nvme3_gb` int DEFAULT '0' COMMENT 'NVME диск 3 в ГБ',
  `nvme4_gb` int DEFAULT '0' COMMENT 'NVME диск 4 в ГБ',
  `nvme5_gb` int DEFAULT '0' COMMENT 'NVME диск 5 в ГБ',
  `hdd_gb` int DEFAULT '0' COMMENT 'Объем HDD диска в ГБ',
  `cpu_price` decimal(10,4) NOT NULL COMMENT 'Цена за ядро',
  `ram_price` decimal(10,4) NOT NULL COMMENT 'Цена за ГБ RAM',
  `nvme_price` decimal(10,4) NOT NULL COMMENT 'Цена за ГБ NVME',
  `hdd_price` decimal(10,4) NOT NULL COMMENT 'Цена за ГБ HDD',
  `cpu_cost` decimal(10,2) NOT NULL COMMENT 'Стоимость CPU',
  `ram_cost` decimal(10,2) NOT NULL COMMENT 'Стоимость RAM',
  `nvme_cost` decimal(10,2) NOT NULL COMMENT 'Стоимость NVME',
  `hdd_cost` decimal(10,2) NOT NULL COMMENT 'Стоимость HDD',
  `total_cost` decimal(10,2) NOT NULL COMMENT 'Общая стоимость',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_daily_billing_vm_date` (`vm_id`,`billing_date`),
  KEY `idx_daily_billing_date` (`billing_date`),
  KEY `idx_daily_billing_client` (`client_id`),
  KEY `idx_daily_billing_vm` (`vm_id`),
  KEY `idx_daily_billing_client_date` (`client_id`,`billing_date`),
  CONSTRAINT `fk_daily_billing_client` FOREIGN KEY (`client_id`) REFERENCES `clients` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_daily_billing_vm` FOREIGN KEY (`vm_id`) REFERENCES `virtual_servers` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `chk_billing_costs_non_negative` CHECK (((`cpu_cost` >= 0) and (`ram_cost` >= 0) and (`nvme_cost` >= 0) and (`hdd_cost` >= 0) and (`total_cost` >= 0)))
) ENGINE=InnoDB AUTO_INCREMENT=19789 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Ежедневный биллинг';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `physical_servers`
--

DROP TABLE IF EXISTS `physical_servers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `physical_servers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Уникальное имя сервера',
  `total_cores` int NOT NULL COMMENT 'Общее количество ядер CPU',
  `total_ram_gb` int NOT NULL COMMENT 'Общий объем RAM в ГБ',
  `total_nvme_gb` int DEFAULT '0' COMMENT 'Общий объем NVME дисков в ГБ',
  `total_sata_gb` int DEFAULT '0' COMMENT 'Общий объем SATA дисков в ГБ',
  `notes` text COLLATE utf8mb4_unicode_ci COMMENT 'Дополнительные заметки',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `idx_physical_servers_name` (`name`),
  KEY `idx_physical_servers_created_at` (`created_at`),
  CONSTRAINT `chk_cores_positive` CHECK ((`total_cores` > 0)),
  CONSTRAINT `chk_nvme_non_negative` CHECK ((`total_nvme_gb` >= 0)),
  CONSTRAINT `chk_ram_positive` CHECK ((`total_ram_gb` > 0)),
  CONSTRAINT `chk_sata_non_negative` CHECK ((`total_sata_gb` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=36 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Физические серверы дата-центра';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_prices`
--

DROP TABLE IF EXISTS `resource_prices`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `resource_prices` (
  `id` int NOT NULL AUTO_INCREMENT,
  `effective_from` date NOT NULL COMMENT 'Дата начала действия цен',
  `cpu_price_per_core` decimal(10,4) NOT NULL COMMENT 'Цена за ядро в день',
  `ram_price_per_gb` decimal(10,4) NOT NULL COMMENT 'Цена за ГБ RAM в день',
  `nvme_price_per_gb` decimal(10,4) NOT NULL COMMENT 'Цена за ГБ NVME в день',
  `hdd_price_per_gb` decimal(10,4) NOT NULL COMMENT 'Цена за ГБ HDD в день',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_resource_prices_date` (`effective_from`),
  KEY `idx_resource_prices_date` (`effective_from`),
  CONSTRAINT `chk_cpu_price_positive` CHECK ((`cpu_price_per_core` > 0)),
  CONSTRAINT `chk_hdd_price_positive` CHECK ((`hdd_price_per_gb` > 0)),
  CONSTRAINT `chk_nvme_price_positive` CHECK ((`nvme_price_per_gb` > 0)),
  CONSTRAINT `chk_ram_price_positive` CHECK ((`ram_price_per_gb` > 0))
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Цены на ресурсы';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `virtual_servers`
--

DROP TABLE IF EXISTS `virtual_servers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `virtual_servers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Имя виртуального сервера',
  `client_id` int NOT NULL COMMENT 'ID клиента',
  `physical_server_id` int NOT NULL COMMENT 'ID физического сервера',
  `status_id` int NOT NULL COMMENT 'ID статуса',
  `purpose` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Назначение сервера',
  `os` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Операционная система',
  `ip_address` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'IPv4 или IPv6 адрес',
  `ip_port` int DEFAULT '22' COMMENT 'Порт для подключения',
  `domain_address` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Доменное имя',
  `domain_port` int DEFAULT '443' COMMENT 'Порт для домена',
  `cpu_cores` int NOT NULL COMMENT 'Количество ядер CPU',
  `ram_gb` int NOT NULL COMMENT 'Объем RAM в ГБ',
  `nvme1_gb` int DEFAULT '0' COMMENT 'NVME диск 1 в ГБ',
  `nvme2_gb` int DEFAULT '0' COMMENT 'NVME диск 2 в ГБ',
  `nvme3_gb` int DEFAULT '0' COMMENT 'NVME диск 3 в ГБ',
  `nvme4_gb` int DEFAULT '0' COMMENT 'NVME диск 4 в ГБ',
  `nvme5_gb` int DEFAULT '0' COMMENT 'NVME диск 5 в ГБ',
  `hdd_gb` int DEFAULT '0' COMMENT 'Объем HDD диска в ГБ',
  `start_date` date DEFAULT NULL COMMENT 'Дата начала использования',
  `stop_date` date DEFAULT NULL COMMENT 'Дата остановки (для удаленных ВМ)',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_virtual_servers_name` (`name`),
  KEY `idx_virtual_servers_client` (`client_id`),
  KEY `idx_virtual_servers_physical` (`physical_server_id`),
  KEY `idx_virtual_servers_status` (`status_id`),
  KEY `idx_virtual_servers_ip` (`ip_address`),
  KEY `idx_virtual_servers_dates` (`start_date`,`stop_date`),
  CONSTRAINT `fk_virtual_servers_client` FOREIGN KEY (`client_id`) REFERENCES `clients` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_virtual_servers_physical` FOREIGN KEY (`physical_server_id`) REFERENCES `physical_servers` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_virtual_servers_status` FOREIGN KEY (`status_id`) REFERENCES `vm_statuses` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `chk_vm_cpu_positive` CHECK ((`cpu_cores` > 0)),
  CONSTRAINT `chk_vm_domain_port_range` CHECK ((`domain_port` between 1 and 65535)),
  CONSTRAINT `chk_vm_hdd_non_negative` CHECK ((`hdd_gb` >= 0)),
  CONSTRAINT `chk_vm_ip_port_range` CHECK ((`ip_port` between 1 and 65535)),
  CONSTRAINT `chk_vm_nvme_ranges` CHECK (((`nvme1_gb` >= 0) and (`nvme2_gb` >= 0) and (`nvme3_gb` >= 0) and (`nvme4_gb` >= 0) and (`nvme5_gb` >= 0))),
  CONSTRAINT `chk_vm_ram_positive` CHECK ((`ram_gb` > 0))
) ENGINE=InnoDB AUTO_INCREMENT=302 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Виртуальные серверы';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vm_config_history`
--

DROP TABLE IF EXISTS `vm_config_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `vm_config_history` (
  `id` int NOT NULL AUTO_INCREMENT,
  `vm_id` int NOT NULL COMMENT 'ID виртуального сервера',
  `effective_from` date NOT NULL COMMENT 'Дата начала действия конфигурации',
  `cpu_cores` int NOT NULL COMMENT 'Количество ядер CPU',
  `ram_gb` int NOT NULL COMMENT 'Объем RAM в ГБ',
  `nvme1_gb` int DEFAULT '0' COMMENT 'NVME диск 1 в ГБ',
  `nvme2_gb` int DEFAULT '0' COMMENT 'NVME диск 2 в ГБ',
  `nvme3_gb` int DEFAULT '0' COMMENT 'NVME диск 3 в ГБ',
  `nvme4_gb` int DEFAULT '0' COMMENT 'NVME диск 4 в ГБ',
  `nvme5_gb` int DEFAULT '0' COMMENT 'NVME диск 5 в ГБ',
  `hdd_gb` int DEFAULT '0' COMMENT 'Объем HDD диска в ГБ',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_vm_config_history_vm_date` (`vm_id`,`effective_from`),
  KEY `idx_vm_config_history_vm` (`vm_id`),
  KEY `idx_vm_config_history_date` (`effective_from`),
  CONSTRAINT `fk_vm_config_history_vm` FOREIGN KEY (`vm_id`) REFERENCES `virtual_servers` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `chk_hist_cpu_positive` CHECK ((`cpu_cores` > 0)),
  CONSTRAINT `chk_hist_hdd_non_negative` CHECK ((`hdd_gb` >= 0)),
  CONSTRAINT `chk_hist_nvme_ranges` CHECK (((`nvme1_gb` >= 0) and (`nvme2_gb` >= 0) and (`nvme3_gb` >= 0) and (`nvme4_gb` >= 0) and (`nvme5_gb` >= 0))),
  CONSTRAINT `chk_hist_ram_positive` CHECK ((`ram_gb` > 0))
) ENGINE=InnoDB AUTO_INCREMENT=62 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='История изменений конфигураций виртуальных машин';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vm_statuses`
--

DROP TABLE IF EXISTS `vm_statuses`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `vm_statuses` (
  `id` int NOT NULL AUTO_INCREMENT,
  `code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Уникальный код статуса (draft, active, deleted)',
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Отображаемое название статуса',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  KEY `idx_vm_statuses_code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Статусы виртуальных машин';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping events for database 'billing'
--

--
-- Dumping routines for database 'billing'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-04-01 14:15:15
