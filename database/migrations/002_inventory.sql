-- ============================================================
-- RestoMate AI - Migration 002
-- Inventory, recipes, suppliers and purchasing.
-- No recipes or ingredient quantities are invented: managers
-- configure them explicitly through the inventory screens.
-- ============================================================
USE bremer;
SET NAMES utf8mb4;

CREATE TABLE suppliers (
  supplier_id   INT AUTO_INCREMENT PRIMARY KEY,
  supplier_name VARCHAR(150) NOT NULL,
  contact_name  VARCHAR(120) NULL,
  phone         VARCHAR(30) NULL,
  email         VARCHAR(255) NULL,
  address       TEXT NULL,
  notes         TEXT NULL,
  is_active     TINYINT(1) NOT NULL DEFAULT 1,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_suppliers_name (supplier_name),
  INDEX idx_suppliers_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE ingredients (
  ingredient_id        INT AUTO_INCREMENT PRIMARY KEY,
  ingredient_name      VARCHAR(150) NOT NULL,
  ingredient_name_ar   VARCHAR(150) NULL,
  unit_of_measure      VARCHAR(20) NOT NULL,
  minimum_stock        DECIMAL(12,3) NOT NULL DEFAULT 0,
  safety_stock         DECIMAL(12,3) NOT NULL DEFAULT 0,
  lead_time_days       INT NOT NULL DEFAULT 2,
  cost_per_unit        DECIMAL(12,4) NULL,
  default_supplier_id  INT NULL,
  is_active            TINYINT(1) NOT NULL DEFAULT 1,
  notes                TEXT NULL,
  created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_ingredients_supplier FOREIGN KEY (default_supplier_id)
      REFERENCES suppliers (supplier_id) ON DELETE SET NULL,
  CONSTRAINT chk_ingredients_min_stock CHECK (minimum_stock >= 0),
  CONSTRAINT chk_ingredients_safety    CHECK (safety_stock >= 0),
  UNIQUE KEY uq_ingredients_name (ingredient_name),
  INDEX idx_ingredients_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE inventory_stock (
  stock_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
  ingredient_id INT NOT NULL,
  quantity      DECIMAL(12,3) NOT NULL DEFAULT 0,
  last_updated  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  updated_by    INT NULL,
  CONSTRAINT fk_stock_ingredient FOREIGN KEY (ingredient_id)
      REFERENCES ingredients (ingredient_id) ON DELETE CASCADE,
  CONSTRAINT fk_stock_user FOREIGN KEY (updated_by)
      REFERENCES users (user_id) ON DELETE SET NULL,
  CONSTRAINT chk_stock_quantity CHECK (quantity >= 0),
  UNIQUE KEY uq_stock_ingredient (ingredient_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE menu_item_ingredients (
  menu_item_ingredient_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  item_id        INT NOT NULL,
  ingredient_id  INT NOT NULL,
  quantity       DECIMAL(12,3) NOT NULL,
  unit_of_measure VARCHAR(20) NOT NULL,
  notes          VARCHAR(255) NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_recipe_item FOREIGN KEY (item_id)
      REFERENCES menu_items (item_id) ON DELETE CASCADE,
  CONSTRAINT fk_recipe_ingredient FOREIGN KEY (ingredient_id)
      REFERENCES ingredients (ingredient_id) ON DELETE CASCADE,
  CONSTRAINT chk_recipe_quantity CHECK (quantity > 0),
  UNIQUE KEY uq_recipe (item_id, ingredient_id),
  INDEX idx_recipe_ingredient (ingredient_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE stock_movements (
  movement_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
  ingredient_id   INT NOT NULL,
  movement_type   ENUM('initial','purchase','consumption','adjustment','waste','return') NOT NULL,
  quantity_change DECIMAL(12,3) NOT NULL,
  quantity_after  DECIMAL(12,3) NOT NULL,
  reason          VARCHAR(255) NULL,
  reference_type  VARCHAR(40) NULL,
  reference_id    VARCHAR(60) NULL,
  order_id        INT NULL,
  purchase_order_id BIGINT NULL,
  user_id         INT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_movement_ingredient FOREIGN KEY (ingredient_id)
      REFERENCES ingredients (ingredient_id) ON DELETE CASCADE,
  CONSTRAINT fk_movement_order FOREIGN KEY (order_id)
      REFERENCES orders (order_id) ON DELETE SET NULL,
  CONSTRAINT fk_movement_user FOREIGN KEY (user_id)
      REFERENCES users (user_id) ON DELETE SET NULL,
  CONSTRAINT chk_movement_after CHECK (quantity_after >= 0),
  INDEX idx_movements_ingredient (ingredient_id, created_at),
  INDEX idx_movements_type (movement_type),
  INDEX idx_movements_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE purchase_orders (
  purchase_order_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  supplier_id       INT NOT NULL,
  status            ENUM('draft','ordered','partially_received','received','cancelled')
      NOT NULL DEFAULT 'draft',
  order_date        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expected_date     DATE NULL,
  received_at       DATETIME NULL,
  total_amount      DECIMAL(12,2) NOT NULL DEFAULT 0,
  notes             TEXT NULL,
  created_by        INT NULL,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_po_supplier FOREIGN KEY (supplier_id)
      REFERENCES suppliers (supplier_id),
  CONSTRAINT fk_po_user FOREIGN KEY (created_by)
      REFERENCES users (user_id) ON DELETE SET NULL,
  CONSTRAINT chk_po_total CHECK (total_amount >= 0),
  INDEX idx_po_status (status),
  INDEX idx_po_supplier (supplier_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE purchase_order_items (
  purchase_order_item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  purchase_order_id BIGINT NOT NULL,
  ingredient_id     INT NOT NULL,
  quantity_ordered  DECIMAL(12,3) NOT NULL,
  quantity_received DECIMAL(12,3) NOT NULL DEFAULT 0,
  unit_cost         DECIMAL(12,4) NULL,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_poi_order FOREIGN KEY (purchase_order_id)
      REFERENCES purchase_orders (purchase_order_id) ON DELETE CASCADE,
  CONSTRAINT fk_poi_ingredient FOREIGN KEY (ingredient_id)
      REFERENCES ingredients (ingredient_id),
  CONSTRAINT chk_poi_ordered  CHECK (quantity_ordered > 0),
  CONSTRAINT chk_poi_received CHECK (quantity_received >= 0),
  CONSTRAINT chk_poi_unit_cost CHECK (unit_cost IS NULL OR unit_cost >= 0),
  UNIQUE KEY uq_poi (purchase_order_id, ingredient_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE stock_movements
  ADD CONSTRAINT fk_movement_purchase FOREIGN KEY (purchase_order_id)
      REFERENCES purchase_orders (purchase_order_id) ON DELETE SET NULL;

-- One row per order guarantees ingredient consumption can never be
-- applied twice, even when staff change status repeatedly.
CREATE TABLE order_stock_applications (
  order_id    INT PRIMARY KEY,
  status      ENUM('applied','reversed') NOT NULL DEFAULT 'applied',
  applied_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  applied_by  INT NULL,
  reversed_at DATETIME NULL,
  reversed_by INT NULL,
  note        VARCHAR(255) NULL,
  CONSTRAINT fk_osa_order FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
  CONSTRAINT fk_osa_applied_by FOREIGN KEY (applied_by) REFERENCES users (user_id) ON DELETE SET NULL,
  CONSTRAINT fk_osa_reversed_by FOREIGN KEY (reversed_by) REFERENCES users (user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
