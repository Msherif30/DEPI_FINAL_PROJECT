-- ============================================================================
-- RestoMate AI - OPTIONAL demo inventory seed
-- ============================================================================
-- STATUS: NOT APPLIED to the delivered live database.
--
-- The source notebook (`DataBase.ipynb`) contains no ingredient list, recipe
-- quantities, supplier records or opening stock. Everything below is clearly
-- labelled DEMO data invented for training/demo purposes. It is provided so a
-- reviewer can exercise the inventory, recipe, purchasing and forecasting
-- screens without typing 20 ingredients by hand.
--
-- It does NOT touch categories, menu_items, customers, orders, order_items or
-- users. No recipe is created: recipe quantities must still be configured by a
-- manager (Inventory -> Recipes), because inventing them would silently change
-- order stock consumption.
--
-- Idempotent:
--   * suppliers / ingredients use INSERT IGNORE (unique names);
--   * inventory_stock uses INSERT IGNORE (unique ingredient_id) so re-running
--     never overwrites a quantity a manager already adjusted;
--   * the opening `initial` movement is only inserted when that ingredient has
--     no movement row at all.
--
-- Apply (review first):
--   mysql -uroot -p bremer < database/seeds/demo_inventory.sql
--
-- Remove again:
--   mysql -uroot -p bremer < database/maintenance/cleanup_demo_inventory.sql
-- ============================================================================

USE bremer;
SET NAMES utf8mb4;

START TRANSACTION;

-- ---------------------------------------------------------------------------
-- Suppliers (fictional demo vendors)
-- ---------------------------------------------------------------------------
INSERT IGNORE INTO suppliers
  (supplier_name, contact_name, phone, email, address, notes, is_active)
VALUES
  ('Cairo Fresh Produce',   'Mona Adel',    '+20 100 000 1001', 'orders@cairo-fresh.example',  'Nasr City, Cairo',      'DEMO supplier - vegetables and fruit', 1),
  ('Delta Meat & Poultry',  'Karim Fathy',  '+20 100 000 1002', 'sales@delta-meat.example',    '6th of October, Giza',  'DEMO supplier - beef, chicken, cheese', 1),
  ('Nile Dry Goods',        'Hala Samir',   '+20 100 000 1003', 'supply@nile-dry.example',     'Shubra, Cairo',         'DEMO supplier - dry goods and bakery', 1),
  ('Alex Beverage Co.',     'Tarek Nabil',  '+20 100 000 1004', 'trade@alex-beverage.example', 'Sidi Gaber, Alexandria','DEMO supplier - soft drinks and water', 1);

-- ---------------------------------------------------------------------------
-- Ingredients (20 demo stock items, Arabic names included)
-- unit_of_measure is a free-text label, not a conversion system.
-- ---------------------------------------------------------------------------
INSERT IGNORE INTO ingredients
  (ingredient_name, ingredient_name_ar, unit_of_measure, minimum_stock, safety_stock,
   lead_time_days, cost_per_unit, default_supplier_id, is_active, notes)
VALUES
  ('Beef patty',        'قرص برجر بقري',   'piece', 40,  20,  4, 18.5000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Delta Meat & Poultry'), 1, 'DEMO value'),
  ('Chicken breast',    'صدور فراخ',       'kg',    15,   8,  3, 145.0000,(SELECT supplier_id FROM suppliers WHERE supplier_name='Delta Meat & Poultry'), 1, 'DEMO value'),
  ('Burger bun',        'عيش برجر',        'piece', 60,  30,  2,  4.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Nile Dry Goods'),        1, 'DEMO value'),
  ('Potato',            'بطاطس',           'kg',    25,  10,  3, 22.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Cairo Fresh Produce'),   1, 'DEMO value'),
  ('Tomato',            'طماطم',           'kg',     8,   4,  2, 14.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Cairo Fresh Produce'),   1, 'DEMO value'),
  ('Lettuce',           'خس',              'kg',     6,   3,  2, 18.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Cairo Fresh Produce'),   1, 'DEMO value'),
  ('Onion',             'بصل',             'kg',    10,   5,  3, 11.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Cairo Fresh Produce'),   1, 'DEMO value'),
  ('Pickles',           'مخلل',            'kg',     4,   2,  5, 35.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Cairo Fresh Produce'),   1, 'DEMO value'),
  ('Cheddar cheese',    'جبنة شيدر',       'kg',     5,   2,  5, 210.0000,(SELECT supplier_id FROM suppliers WHERE supplier_name='Delta Meat & Poultry'), 1, 'DEMO value'),
  ('Mozzarella cheese', 'جبنة موتزاريلا',  'kg',     5,   2,  5, 195.0000,(SELECT supplier_id FROM suppliers WHERE supplier_name='Delta Meat & Poultry'), 1, 'DEMO value'),
  ('Pizza dough',       'عجينة بيتزا',     'kg',    12,   5,  2, 30.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Nile Dry Goods'),        1, 'DEMO value'),
  ('Tomato paste',      'صلصة طماطم',      'kg',     6,   3,  7, 42.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Nile Dry Goods'),        1, 'DEMO value'),
  ('Rice',              'أرز',             'kg',    20,  10,  7, 28.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Nile Dry Goods'),        1, 'DEMO value'),
  ('Pasta',             'مكرونة',          'kg',    15,   8,  7, 24.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Nile Dry Goods'),        1, 'DEMO value'),
  ('Cooking oil',       'زيت طهي',         'liter', 18,   9,  5, 65.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Nile Dry Goods'),        1, 'DEMO value'),
  ('Mayonnaise',        'مايونيز',         'kg',     5,   2,  6, 55.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Nile Dry Goods'),        1, 'DEMO value'),
  ('Ketchup',           'كاتشب',           'kg',     5,   2,  6, 38.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Nile Dry Goods'),        1, 'DEMO value'),
  ('Cola syrup',        'شراب كولا',       'liter',  8,   4,  4, 70.0000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Alex Beverage Co.'),    1, 'DEMO value'),
  ('Bottled water',     'مياه معبأة',      'piece', 96,  48,  3,  3.5000, (SELECT supplier_id FROM suppliers WHERE supplier_name='Alex Beverage Co.'),    1, 'DEMO value'),
  ('Coffee beans',      'بن',              'kg',     4,   2, 10, 320.0000,(SELECT supplier_id FROM suppliers WHERE supplier_name='Nile Dry Goods'),        1, 'DEMO value');

-- ---------------------------------------------------------------------------
-- Opening balances
-- Quantities are arbitrary DEMO levels (roughly 2-4x the minimum) chosen only
-- so the low-stock warnings and recommendations have something to work with.
-- ---------------------------------------------------------------------------
INSERT IGNORE INTO inventory_stock (ingredient_id, quantity, updated_by)
SELECT i.ingredient_id,
       CASE i.ingredient_name
         WHEN 'Beef patty'        THEN 160.000
         WHEN 'Chicken breast'    THEN  30.000
         WHEN 'Burger bun'        THEN 240.000
         WHEN 'Potato'            THEN  80.000
         WHEN 'Tomato'            THEN  25.000
         WHEN 'Lettuce'           THEN  18.000
         WHEN 'Onion'             THEN  35.000
         WHEN 'Pickles'           THEN  12.000
         WHEN 'Cheddar cheese'    THEN  16.000
         WHEN 'Mozzarella cheese' THEN  15.000
         WHEN 'Pizza dough'       THEN  40.000
         WHEN 'Tomato paste'      THEN  20.000
         WHEN 'Rice'              THEN  60.000
         WHEN 'Pasta'             THEN  45.000
         WHEN 'Cooking oil'       THEN  50.000
         WHEN 'Mayonnaise'        THEN  14.000
         WHEN 'Ketchup'           THEN  14.000
         WHEN 'Cola syrup'        THEN  24.000
         WHEN 'Bottled water'     THEN 288.000
         WHEN 'Coffee beans'      THEN  12.000
       END,
       (SELECT user_id FROM users WHERE role = 'manager' ORDER BY user_id LIMIT 1)
FROM ingredients i
WHERE i.ingredient_name IN (
  'Beef patty','Chicken breast','Burger bun','Potato','Tomato','Lettuce','Onion',
  'Pickles','Cheddar cheese','Mozzarella cheese','Pizza dough','Tomato paste',
  'Rice','Pasta','Cooking oil','Mayonnaise','Ketchup','Cola syrup','Bottled water',
  'Coffee beans'
);

-- ---------------------------------------------------------------------------
-- Matching opening ledger rows (only when the ingredient has no movement yet)
-- ---------------------------------------------------------------------------
INSERT INTO stock_movements
  (ingredient_id, movement_type, quantity_change, quantity_after, reason,
   reference_type, reference_id, user_id)
SELECT s.ingredient_id, 'initial', s.quantity, s.quantity,
       'DEMO opening balance (optional seed, not production data)',
       'seed', 'demo_inventory', s.updated_by
FROM inventory_stock s
JOIN ingredients i ON i.ingredient_id = s.ingredient_id
WHERE i.ingredient_name IN (
  'Beef patty','Chicken breast','Burger bun','Potato','Tomato','Lettuce','Onion',
  'Pickles','Cheddar cheese','Mozzarella cheese','Pizza dough','Tomato paste',
  'Rice','Pasta','Cooking oil','Mayonnaise','Ketchup','Cola syrup','Bottled water',
  'Coffee beans'
)
AND NOT EXISTS (
  SELECT 1 FROM stock_movements m WHERE m.ingredient_id = s.ingredient_id
);

COMMIT;

-- Expected result after applying:
--   suppliers         4 new demo rows
--   ingredients      20 new demo rows
--   inventory_stock  20 rows
--   stock_movements  20 `initial` rows
-- Nothing else changes: menu, customers, orders and recipe tables are untouched.
