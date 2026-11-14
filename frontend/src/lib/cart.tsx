import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export interface CartLine {
  item_id: number;
  item_name: string;
  item_name_ar?: string | null;
  price: number;
  quantity: number;
}

interface CartValue {
  lines: CartLine[];
  subtotal: number;
  count: number;
  add: (line: Omit<CartLine, "quantity">, quantity?: number) => void;
  setQuantity: (itemId: number, quantity: number) => void;
  remove: (itemId: number) => void;
  clear: () => void;
}

const STORAGE_KEY = "rm_cart";
const CartContext = createContext<CartValue | null>(null);

function load(): CartLine[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as CartLine[]) : [];
  } catch {
    return [];
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(load);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
  }, [lines]);

  const add = useCallback((line: Omit<CartLine, "quantity">, quantity = 1) => {
    setLines((prev) => {
      const found = prev.find((row) => row.item_id === line.item_id);
      if (found) {
        return prev.map((row) =>
          row.item_id === line.item_id ? { ...row, quantity: Math.min(99, row.quantity + quantity) } : row
        );
      }
      return [...prev, { ...line, quantity: Math.min(99, quantity) }];
    });
  }, []);

  const setQuantity = useCallback((itemId: number, quantity: number) => {
    setLines((prev) => {
      if (quantity <= 0) return prev.filter((row) => row.item_id !== itemId);
      return prev.map((row) => (row.item_id === itemId ? { ...row, quantity: Math.min(99, quantity) } : row));
    });
  }, []);

  const remove = useCallback((itemId: number) => {
    setLines((prev) => prev.filter((row) => row.item_id !== itemId));
  }, []);

  const clear = useCallback(() => setLines([]), []);

  const subtotal = useMemo(
    () => lines.reduce((sum, row) => sum + Number(row.price) * row.quantity, 0),
    [lines]
  );
  const count = useMemo(() => lines.reduce((sum, row) => sum + row.quantity, 0), [lines]);

  const value = useMemo(
    () => ({ lines, subtotal, count, add, setQuantity, remove, clear }),
    [lines, subtotal, count, add, setQuantity, remove, clear]
  );
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside CartProvider");
  return ctx;
}
