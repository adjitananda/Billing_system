-- Таблица конкурентов
CREATE TABLE IF NOT EXISTS competitors (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    website VARCHAR(255),
    logo_url VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица цен конкурентов
CREATE TABLE IF NOT EXISTS competitor_prices (
    id INT PRIMARY KEY AUTO_INCREMENT,
    competitor_id INT NOT NULL UNIQUE,
    cpu_price DECIMAL(10,4) NOT NULL DEFAULT 0,
    ram_price DECIMAL(10,4) NOT NULL DEFAULT 0,
    nvme_price DECIMAL(10,4) NOT NULL DEFAULT 0,
    hdd_price DECIMAL(10,4) NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (competitor_id) REFERENCES competitors(id) ON DELETE CASCADE
);
