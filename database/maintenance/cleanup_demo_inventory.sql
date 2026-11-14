-- ============================================================================
-- RestoMate AI - remove the OPTIONAL demo inventory seed
-- ============================================================================
-- Counterpart to `database/seeds/demo_inventory.sql`.
--
-- It removes only rows that the demo seed created and that a manager has not
-- since reused:
--   * stock movements tagged reference_type = 'seed' / reference_id = 'demo_inventory'
--   * opening balances for the 20 demo ingredients
--   * demo ingredients that are not referenced by any recipe or purchase order
--   * the four demo suppliers that have no purchase orders and are not the
--     default supplier of a remaining ingredient
--
-- Menu items, customers, orders, order_items, users and recipes are untouched.
-- Take a backup before running against any database that matters.
-- ============================================================================

USE bremer;
SET NAMES utf8mb4;

START TRANSACTION;

-- 1. Demo ledger rows first (FK to ingredients/inventory would block otherwise).
DELETE FROM stock_movements
WHERE reference_type = 'seed'
  AND reference_id = 'demo_inventory';

-- 2. Demo balances.
DELETE s
FROM inventory_stock s
JOIN ingredients i ON i.ingredient_id = s.ingredient_id
WHERE i.ingredient_name IN (
  'Beef patty','Chicken breast','Burger bun','Potato','Tomato','Lettuce','Onion',
  'Pickles','Cheddar cheese','Mozzarella cheese','Pizza dough','Tomato paste',
  'Rice','Pasta','Cooking oil','Mayonnaise','Ketchup','Cola syrup','Bottled water',
  'Coffee beans'
);

-- 3. Demo ingredients without any remaining reference.
DELETE i
FROM ingredients i
WHERE i.ingredient_name IN (
  'Beef patty','Chicken breast','Burger bun','Potato','Tomato','Lettuce','Onion',
  'Pickles','Cheddar cheese','Mozzarella cheese','Pizza dough','Tomato paste',
  'Rice','Pasta','Cooking oil','Mayonnaise','Ketchup','Cola syrup','Bottled water',
  'Coffee beans'
)
AND NOT EXISTS (SELECT 1 FROM menu_item_ingredients r WHERE r.ingredient_id = i.ingredient_id)
AND NOT EXISTS (SELECT 1 FROM purchase_order_items p WHERE p.ingredient_id = i.ingredient_id)
AND NOT EXISTS (SELECT 1 FROM stock_movements m WHERE m.ingredient_id = i.ingredient_id);

-- 4. Demo suppliers that are no longer referenced.
DELETE s
FROM suppliers s
WHERE s.supplier_name IN (
  'Cairo Fresh Produce','Delta Meat & Poultry','Nile Dry Goods','Alex Beverage Co.'
)
AND NOT EXISTS (SELECT 1 FROM purchase_orders p WHERE p.supplier_id = s.supplier_id)
AND NOT EXISTS (SELECT 1 FROM ingredients i WHERE i.default_supplier_id = s.supplier_id);

COMMIT;

-- Expected result: the inventory tables return to their pre-seed state
-- (empty unless the manager added their own records in the meantime).
