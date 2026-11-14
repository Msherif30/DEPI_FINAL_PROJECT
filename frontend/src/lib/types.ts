export type Role = "customer" | "chef" | "cashier" | "manager";

export interface User {
  user_id: number;
  username: string;
  email?: string | null;
  full_name?: string | null;
  role: Role;
  is_active: boolean;
  created_at?: string | null;
  last_login_at?: string | null;
  has_pin: boolean;
}

export interface CustomerProfile {
  customer_id: number;
  customer_name?: string | null;
  phone?: string | null;
  address?: string | null;
  created_at?: string | null;
}

export interface Category {
  category_id: number;
  category_name: string;
  category_name_ar?: string | null;
  description?: string | null;
  image_url?: string | null;
  is_active: boolean;
  item_count: number;
}

export interface MenuItem {
  item_id: number;
  category_id: number;
  category_name?: string | null;
  category_name_ar?: string | null;
  item_name: string;
  item_name_ar: string;
  synonyms?: string | null;
  price: number;
  is_available: boolean;
  description?: string | null;
  description_ar?: string | null;
  image_url?: string | null;
  preparation_time?: number | null;
  is_featured: boolean;
  created_at?: string | null;
}

export interface OrderItem {
  order_item_id: number;
  item_id: number;
  item_name_snapshot?: string | null;
  item_name_ar?: string | null;
  quantity: number;
  unit_price: number;
  line_total: number;
  special_instructions?: string | null;
}

export interface Payment {
  payment_id: number;
  payment_method: string;
  payment_status: string;
  amount: number;
  transaction_reference?: string | null;
  paid_at?: string | null;
  created_at?: string | null;
}

export interface StatusHistory {
  history_id: number;
  previous_status?: string | null;
  new_status: string;
  changed_by?: number | null;
  changed_by_name?: string | null;
  changed_at?: string | null;
  notes?: string | null;
}

export type OrderStatus = "pending" | "confirmed" | "preparing" | "completed" | "cancelled";
export type PaymentStatus = "unpaid" | "pending" | "paid" | "refunded" | "partially_refunded";

export interface Order {
  order_id: number;
  customer_id?: number | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  order_date: string;
  updated_at?: string | null;
  status: OrderStatus;
  payment_status: PaymentStatus;
  payment_method?: string | null;
  order_notes?: string | null;
  order_source: string;
  total_amount: number;
  items: OrderItem[];
  payments: Payment[];
  status_history: StatusHistory[];
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages?: number;
}

export interface Ingredient {
  ingredient_id: number;
  ingredient_name: string;
  ingredient_name_ar?: string | null;
  unit_of_measure: string;
  minimum_stock: number;
  safety_stock: number;
  lead_time_days: number;
  cost_per_unit?: number | null;
  default_supplier_id?: number | null;
  is_active: boolean;
  quantity_on_hand: number;
  stock_status: "ok" | "low" | "critical" | "unknown" | string;
  has_recipe: boolean;
}

export interface StockMovement {
  movement_id: number;
  ingredient_id: number;
  ingredient_name?: string | null;
  movement_type: string;
  quantity_change: number;
  quantity_after: number;
  reason?: string | null;
  reference_type?: string | null;
  reference_id?: string | null;
  order_id?: number | null;
  purchase_order_id?: number | null;
  user_id?: number | null;
  user_name?: string | null;
  created_at: string;
}

export interface Supplier {
  supplier_id: number;
  supplier_name: string;
  contact_name?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  notes?: string | null;
  is_active: boolean;
}

export interface PurchaseOrderItem {
  purchase_order_item_id: number;
  ingredient_id: number;
  ingredient_name?: string | null;
  unit_of_measure?: string | null;
  quantity_ordered: number;
  quantity_received: number;
  unit_cost?: number | null;
}

export interface PurchaseOrder {
  purchase_order_id: number;
  supplier_id: number;
  supplier_name?: string | null;
  status: string;
  order_date: string;
  expected_date?: string | null;
  received_at?: string | null;
  total_amount: number;
  notes?: string | null;
  created_by?: number | null;
  items: PurchaseOrderItem[];
}

export interface RecipeLine {
  menu_item_ingredient_id: number;
  item_id: number;
  ingredient_id: number;
  ingredient_name?: string | null;
  quantity: number;
  unit_of_measure: string;
  notes?: string | null;
}

export interface Recommendation {
  ingredient_id: number;
  ingredient_name: string;
  unit_of_measure: string;
  current_quantity: number;
  minimum_stock: number;
  safety_stock: number;
  expected_demand: number;
  suggested_quantity: number;
  lead_time_days: number;
  reason: string;
}

export interface KioskCartLine {
  item_id: number;
  item_name: string;
  item_name_ar?: string | null;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface KioskSuggestion {
  item_id: number;
  item_name: string;
  item_name_ar?: string | null;
  price: number;
  description?: string | null;
  description_ar?: string | null;
  image_url?: string | null;
  is_featured: boolean;
}

export interface PaymentMethod {
  code: string;
  name: string;
  name_ar: string;
}

export interface KioskSession {
  session_id: string;
  status: string;
  language: string;
  expires_at: string;
  cart: KioskCartLine[];
  subtotal: number;
  order_id?: number | null;
}

export interface AuditLogEntry {
  audit_id: number;
  user_id?: number | null;
  user_name?: string | null;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  details?: Record<string, unknown> | null;
  ip_address?: string | null;
  created_at: string;
}

export interface KioskChatResponse {
  reply: string;
  state: string;
  cart: KioskCartLine[];
  subtotal: number;
  order_id?: number | null;
  requires_confirmation: boolean;
  suggestions: KioskSuggestion[];
}
