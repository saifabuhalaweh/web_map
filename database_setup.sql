CREATE TABLE IF NOT EXISTS companies (
    company_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    location_string VARCHAR(255),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8)
);

CREATE TABLE IF NOT EXISTS categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) UNIQUE NOT NULL,
    type ENUM('MAIN', 'SUB') NOT NULL
);

CREATE TABLE IF NOT EXISTS company_categories (
    company_id VARCHAR(50),
    category_id INT,
    PRIMARY KEY (company_id, category_id),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
);
