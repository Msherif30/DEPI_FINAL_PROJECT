import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  AlertTriangle,
  ArrowDownCircle,
  ArrowUpCircle,
  Boxes,
  ClipboardList,
  FlaskConical,
  Plus,
  RefreshCw,
  Scale,
  Trash2,
  Wand2
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Loading,
  Modal,
  PageHeader,
  SectionTitle,
  SelectField,
  StatusBadge,
  Tabs,
  TextAreaField,
  TextField,
  useToast
} from "../../components/ui";
import { api, errorMessage, qs } from "../../lib/api";
import { dateTime, money, number } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { Ingredient, MenuItem, Paginated, RecipeLine, Recommendation, StockMovement, Supplier } from "../../lib/types";

type Tab = "ingredients" | "movements" | "recipes" | "recommendations";

interface MovementResponse extends Paginated<StockMovement> {}

export default function Inventory() {
  const { t, pick } = useI18n();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("ingredients");
  const [addOpen, setAddOpen] = useState(false);
  const [adjust, setAdjust] = useState<Ingredient | null>(null);
  const [search, setSearch] = useState("");

  const inventory = useQuery({ queryKey: ["inventory"], queryFn: () => api<Ingredient[]>("/inventory") });
  const lowStock = useQuery({ queryKey: ["low-stock"], queryFn: () => api<Ingredient[]>("/inventory/low-stock") });
  const movements = useQuery({
    queryKey: ["movements"],
    queryFn: () => api<MovementResponse>("/inventory/movements?page=1&page_size=100"),
    enabled: tab === "movements"
  });
  const recommendations = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => api<Recommendation[]>("/inventory/recommendations?horizon_days=7"),
    enabled: tab === "recommendations"
  });
  const suppliers = useQuery({ queryKey: ["suppliers"], queryFn: () => api<Supplier[]>("/suppliers") });

  const filtered = useMemo(() => {
    const rows = inventory.data ?? [];
    if (!search.trim()) return rows;
    const term = search.toLowerCase();
    return rows.filter((row) => `${row.ingredient_name} ${row.ingredient_name_ar ?? ""}`.toLowerCase().includes(term));
  }, [inventory.data, search]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
    queryClient.invalidateQueries({ queryKey: ["low-stock"] });
    queryClient.invalidateQueries({ queryKey: ["movements"] });
    queryClient.invalidateQueries({ queryKey: ["recommendations"] });
  };

  return (
    <div>
      <PageHeader
        eyebrow={pick("Manager", "الإدارة")}
        title={t("inventory.title")}
        subtitle={t("inventory.subtitle")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={() => { void inventory.refetch(); void lowStock.refetch(); }} loading={inventory.isFetching}>
              <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
            </Button>
            <Button onClick={() => setAddOpen(true)}>
              <Plus className="h-4 w-4" /> {t("inventory.addIngredient")}
            </Button>
          </div>
        }
      />

      {(lowStock.data ?? []).length ? (
        <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <p className="text-sm font-bold text-amber-900">{t("inventory.lowStock")}</p>
            <Badge tone="warn">{lowStock.data?.length}</Badge>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {(lowStock.data ?? []).slice(0, 8).map((row) => (
              <button
                key={row.ingredient_id}
                onClick={() => setAdjust(row)}
                className="rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-semibold text-amber-900 hover:bg-amber-100"
              >
                {pick(row.ingredient_name, row.ingredient_name_ar)} · {number(row.quantity_on_hand, 1)} {row.unit_of_measure}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "ingredients", label: t("inventory.ingredients"), icon: <Boxes className="h-4 w-4" />, count: inventory.data?.length },
            { value: "movements", label: t("inventory.movements"), icon: <ClipboardList className="h-4 w-4" /> },
            { value: "recipes", label: t("inventory.recipes"), icon: <FlaskConical className="h-4 w-4" /> },
            { value: "recommendations", label: t("inventory.recommendations"), icon: <Wand2 className="h-4 w-4" /> }
          ]}
        />
        {tab === "ingredients" ? (
          <label className="relative">
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={`${t("common.search")}…`} className="field h-10 w-56" />
          </label>
        ) : null}
      </div>

      {tab === "ingredients" ? (
        inventory.isLoading ? <Loading /> : !inventory.data?.length ? (
          <EmptyState
            title={pick("No ingredients configured", "لا توجد مكونات مسجلة")}
            description={pick("Add ingredients, then attach recipes to menu items to consume stock automatically.", "أضف المكونات ثم اربط الوصفات بالأصناف لخصم المخزون تلقائياً.")}
            action={<Button onClick={() => setAddOpen(true)}><Plus className="h-4 w-4" /> {t("inventory.addIngredient")}</Button>}
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("common.name")}</th>
                    <th>{t("inventory.onHand")}</th>
                    <th>{t("inventory.minimum")}</th>
                    <th>{t("inventory.unit")}</th>
                    <th>{t("inventory.leadTime")}</th>
                    <th>{t("inventory.cost")}</th>
                    <th>{t("common.status")}</th>
                    <th>{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => (
                    <tr key={row.ingredient_id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-50 text-brand-700"><Scale className="h-4 w-4" /></span>
                          <div>
                            <p className="font-semibold text-ink-900">{pick(row.ingredient_name, row.ingredient_name_ar)}</p>
                            {row.has_recipe ? <p className="text-[10px] text-emerald-600">{pick("Used in recipes", "مستخدم في وصفات")}</p> : null}
                          </div>
                        </div>
                      </td>
                      <td className="font-bold text-ink-900">{number(row.quantity_on_hand, 1)} <span className="text-xs font-normal text-ink-400">{row.unit_of_measure}</span></td>
                      <td>{number(row.minimum_stock, 1)}</td>
                      <td>{row.unit_of_measure}</td>
                      <td>{row.lead_time_days} {pick("days", "يوم")}</td>
                      <td>{row.cost_per_unit ? money(row.cost_per_unit) : "—"}</td>
                      <td><StatusBadge status={row.stock_status} /></td>
                      <td>
                        <Button size="sm" variant="secondary" onClick={() => setAdjust(row)}>
                          <ArrowUpCircle className="h-3.5 w-3.5" /> {t("inventory.adjustStock")}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )
      ) : null}

      {tab === "movements" ? (
        movements.isLoading ? <Loading /> : !movements.data?.items.length ? (
          <EmptyState title={t("common.noData")} description={pick("Stock movements appear here after purchases, waste or order preparation.", "تظهر حركات المخزون بعد الشراء أو الهالك أو تحضير الطلبات.")} />
        ) : (
          <Card className="overflow-hidden">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("common.notes")}</th>
                    <th>{t("inventory.movementType")}</th>
                    <th>{t("inventory.change")}</th>
                    <th>{t("inventory.after")}</th>
                    <th>{t("inventory.reason")}</th>
                    <th>{pick("Reference", "المرجع")}</th>
                    <th>{pick("By", "بواسطة")}</th>
                    <th>{t("audit.when")}</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.data.items.map((row) => (
                    <tr key={row.movement_id}>
                      <td className="font-semibold text-ink-900">{row.ingredient_name}</td>
                      <td><Badge tone={row.quantity_change >= 0 ? "success" : "danger"}>{row.movement_type}</Badge></td>
                      <td className={clsx("font-bold", row.quantity_change >= 0 ? "text-emerald-700" : "text-rose-700")}>
                        {row.quantity_change >= 0 ? "+" : ""}{number(row.quantity_change, 2)}
                      </td>
                      <td>{number(row.quantity_after, 2)}</td>
                      <td className="max-w-[240px] truncate">{row.reason ?? "—"}</td>
                      <td className="text-xs text-ink-500">
                        {row.order_id ? `#${row.order_id}` : row.purchase_order_id ? `PO #${row.purchase_order_id}` : row.reference_type ?? "—"}
                      </td>
                      <td>{row.user_name ?? "—"}</td>
                      <td className="whitespace-nowrap text-xs text-ink-500">{dateTime(row.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )
      ) : null}

      {tab === "recipes" ? <RecipesTab ingredients={inventory.data ?? []} /> : null}

      {tab === "recommendations" ? (
        recommendations.isLoading ? <Loading /> : !recommendations.data?.length ? (
          <EmptyState
            title={pick("No purchase recommendations", "لا توجد توصيات شراء")}
            description={pick("Add minimum stock levels and recipes to generate a data-driven purchase plan.", "أضف حدود المخزون والوصفات لتوليد خطة شراء مبنية على البيانات.")}
            icon={<Wand2 className="h-6 w-6" />}
          />
        ) : (
          <Card className="overflow-hidden">
            <div className="border-b border-ink-100 bg-ink-50/60 px-5 py-3 text-xs text-ink-500">
              {pick("Uses completed-order demand and configured recipes. No numbers are invented.", "يعتمد على طلب الطلبات المكتملة والوصفات المسجلة. لا يتم اختراع أرقام.")}
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("common.name")}</th>
                    <th>{t("inventory.onHand")}</th>
                    <th>{pick("Expected demand", "الطلب المتوقع")}</th>
                    <th>{t("inventory.suggested")}</th>
                    <th>{t("inventory.leadTime")}</th>
                    <th>{t("inventory.reason")}</th>
                  </tr>
                </thead>
                <tbody>
                  {recommendations.data.map((row) => (
                    <tr key={row.ingredient_id}>
                      <td className="font-semibold text-ink-900">{row.ingredient_name}</td>
                      <td>{number(row.current_quantity, 1)} {row.unit_of_measure}</td>
                      <td>{number(row.expected_demand, 1)}</td>
                      <td><Badge tone="brand">{number(row.suggested_quantity, 1)} {row.unit_of_measure}</Badge></td>
                      <td>{row.lead_time_days} {pick("days", "يوم")}</td>
                      <td className="max-w-[280px] text-xs">{row.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )
      ) : null}

      <AddIngredientModal
        open={addOpen}
        suppliers={suppliers.data ?? []}
        onClose={() => setAddOpen(false)}
        onSaved={() => {
          setAddOpen(false);
          invalidate();
        }}
      />
      <AdjustStockModal
        ingredient={adjust}
        onClose={() => setAdjust(null)}
        onSaved={() => {
          setAdjust(null);
          invalidate();
        }}
      />
    </div>
  );
}

function AddIngredientModal({
  open,
  suppliers,
  onClose,
  onSaved
}: {
  open: boolean;
  suppliers: Supplier[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t, pick } = useI18n();
  const toast = useToast();
  const [form, setForm] = useState({
    ingredient_name: "",
    ingredient_name_ar: "",
    unit_of_measure: "kg",
    minimum_stock: "0",
    safety_stock: "0",
    lead_time_days: "2",
    cost_per_unit: "",
    default_supplier_id: "",
    initial_stock: "0"
  });

  const mutation = useMutation({
    mutationFn: () =>
      api("/inventory/ingredients", {
        method: "POST",
        body: {
          ingredient_name: form.ingredient_name,
          ingredient_name_ar: form.ingredient_name_ar || undefined,
          unit_of_measure: form.unit_of_measure,
          minimum_stock: Number(form.minimum_stock),
          safety_stock: Number(form.safety_stock),
          lead_time_days: Number(form.lead_time_days),
          cost_per_unit: form.cost_per_unit ? Number(form.cost_per_unit) : undefined,
          default_supplier_id: form.default_supplier_id ? Number(form.default_supplier_id) : undefined,
          initial_stock: Number(form.initial_stock)
        }
      }),
    onSuccess: () => {
      toast.success(pick("Ingredient created", "تم إنشاء المكون"));
      setForm({ ingredient_name: "", ingredient_name_ar: "", unit_of_measure: "kg", minimum_stock: "0", safety_stock: "0", lead_time_days: "2", cost_per_unit: "", default_supplier_id: "", initial_stock: "0" });
      onSaved();
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("inventory.addIngredient")}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button loading={mutation.isPending} onClick={() => mutation.mutate()}>{t("common.save")}</Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField label={t("common.name")} value={form.ingredient_name} onChange={(event) => setForm((prev) => ({ ...prev, ingredient_name: event.target.value }))} required />
        <TextField label={t("menuAdmin.nameAr")} value={form.ingredient_name_ar} onChange={(event) => setForm((prev) => ({ ...prev, ingredient_name_ar: event.target.value }))} />
        <TextField label={t("inventory.unit")} value={form.unit_of_measure} onChange={(event) => setForm((prev) => ({ ...prev, unit_of_measure: event.target.value }))} required />
        <TextField label={t("inventory.leadTime")} type="number" min={0} value={form.lead_time_days} onChange={(event) => setForm((prev) => ({ ...prev, lead_time_days: event.target.value }))} />
        <TextField label={t("inventory.minimum")} type="number" min={0} step="0.01" value={form.minimum_stock} onChange={(event) => setForm((prev) => ({ ...prev, minimum_stock: event.target.value }))} />
        <TextField label={t("inventory.safety")} type="number" min={0} step="0.01" value={form.safety_stock} onChange={(event) => setForm((prev) => ({ ...prev, safety_stock: event.target.value }))} />
        <TextField label={t("inventory.cost")} type="number" min={0} step="0.01" value={form.cost_per_unit} onChange={(event) => setForm((prev) => ({ ...prev, cost_per_unit: event.target.value }))} />
        <TextField label={pick("Initial stock", "الرصيد الافتتاحي")} type="number" min={0} step="0.01" value={form.initial_stock} onChange={(event) => setForm((prev) => ({ ...prev, initial_stock: event.target.value }))} />
        <div className="sm:col-span-2">
          <SelectField label={`${t("purchasing.supplier")} (${t("common.optional")})`} value={form.default_supplier_id} onChange={(event) => setForm((prev) => ({ ...prev, default_supplier_id: event.target.value }))}>
            <option value="">—</option>
            {suppliers.map((supplier) => (
              <option key={supplier.supplier_id} value={supplier.supplier_id}>{supplier.supplier_name}</option>
            ))}
          </SelectField>
        </div>
      </div>
    </Modal>
  );
}

function AdjustStockModal({ ingredient, onClose, onSaved }: { ingredient: Ingredient | null; onClose: () => void; onSaved: () => void }) {
  const { t, pick } = useI18n();
  const toast = useToast();
  const [movementType, setMovementType] = useState("purchase");
  const [direction, setDirection] = useState("increase");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (ingredient) {
      setMovementType("purchase");
      setDirection("increase");
      setQuantity("");
      setReason("");
    }
  }, [ingredient]);

  const mutation = useMutation({
    mutationFn: () =>
      api("/inventory/stock-movements", {
        method: "POST",
        body: {
          ingredient_id: ingredient?.ingredient_id,
          movement_type: movementType,
          quantity: Number(quantity),
          direction,
          reason: reason || undefined
        }
      }),
    onSuccess: () => {
      toast.success(pick("Stock updated", "تم تحديث المخزون"));
      onSaved();
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const effect =
    movementType === "waste" || (movementType === "adjustment" && direction === "decrease") ? -Number(quantity || 0) : Number(quantity || 0);

  return (
    <Modal
      open={Boolean(ingredient)}
      onClose={onClose}
      title={`${t("inventory.adjustStock")} · ${ingredient ? pick(ingredient.ingredient_name, ingredient.ingredient_name_ar) : ""}`}
      description={ingredient ? `${t("inventory.onHand")}: ${number(ingredient.quantity_on_hand, 2)} ${ingredient.unit_of_measure}` : undefined}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{t("common.cancel")}</Button>
          <Button loading={mutation.isPending} disabled={!quantity} onClick={() => mutation.mutate()}>{t("common.save")}</Button>
        </>
      }
    >
      <div className="grid gap-4">
        <SelectField label={t("inventory.movementType")} value={movementType} onChange={(event) => setMovementType(event.target.value)}>
          <option value="purchase">{t("inventory.purchase")}</option>
          <option value="adjustment">{t("inventory.adjustment")}</option>
          <option value="waste">{t("inventory.waste")}</option>
          <option value="return">{pick("Return to supplier", "إرجاع للمورد")}</option>
        </SelectField>
        {movementType === "adjustment" || movementType === "return" ? (
          <SelectField label={pick("Direction", "الاتجاه")} value={direction} onChange={(event) => setDirection(event.target.value)}>
            <option value="increase">{pick("Increase", "زيادة")}</option>
            <option value="decrease">{pick("Decrease", "نقصان")}</option>
          </SelectField>
        ) : null}
        <TextField label={`${t("common.quantity")} (${ingredient?.unit_of_measure ?? ""})`} type="number" min={0.01} step="0.01" value={quantity} onChange={(event) => setQuantity(event.target.value)} required />
        <TextAreaField label={t("inventory.reason")} value={reason} onChange={(event) => setReason(event.target.value)} maxLength={255} />
        <div className="flex items-center justify-between rounded-xl bg-ink-50 px-3.5 py-3 text-sm">
          <span className="font-semibold text-ink-600">{pick("New stock will be", "المخزون الجديد سيكون")}</span>
          <span className="font-display text-base font-extrabold text-ink-900">
            {number((ingredient?.quantity_on_hand ?? 0) + effect, 2)} {ingredient?.unit_of_measure}
          </span>
        </div>
      </div>
    </Modal>
  );
}

function RecipesTab({ ingredients }: { ingredients: Ingredient[] }) {
  const { t, pick } = useI18n();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [itemId, setItemId] = useState<number | "">("");
  const [lines, setLines] = useState<{ ingredient_id: number; quantity: string; unit_of_measure: string; notes: string }[]>([]);

  const menu1 = useQuery({ queryKey: ["menu-recipe-1"], queryFn: () => api<Paginated<MenuItem>>("/menu?page=1&page_size=100&sort=name") });
  const menu2 = useQuery({ queryKey: ["menu-recipe-2"], queryFn: () => api<Paginated<MenuItem>>("/menu?page=2&page_size=100&sort=name") });
  const menuItems = useMemo(() => [...(menu1.data?.items ?? []), ...(menu2.data?.items ?? [])], [menu1.data, menu2.data]);

  const recipe = useQuery({
    queryKey: ["recipe", itemId],
    queryFn: () => api<RecipeLine[]>(`/inventory/recipes/${itemId}`),
    enabled: Boolean(itemId)
  });

  useEffect(() => {
    if (recipe.data) {
      setLines(
        recipe.data.map((line) => ({
          ingredient_id: line.ingredient_id,
          quantity: String(line.quantity),
          unit_of_measure: line.unit_of_measure,
          notes: line.notes ?? ""
        }))
      );
    } else if (itemId) {
      setLines([]);
    }
  }, [recipe.data, itemId]);

  const save = useMutation({
    mutationFn: () =>
      api(`/inventory/recipes/${itemId}`, {
        method: "PUT",
        body: lines.map((line) => ({
          ingredient_id: line.ingredient_id,
          quantity: Number(line.quantity),
          unit_of_measure: line.unit_of_measure,
          notes: line.notes || undefined
        }))
      }),
    onSuccess: () => {
      toast.success(pick("Recipe saved", "تم حفظ الوصفة"));
      queryClient.invalidateQueries({ queryKey: ["recipe", itemId] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
      <Card className="card-pad">
        <SectionTitle title={t("inventory.recipes")} description={pick("Attach ingredients to a menu item. Stock is consumed when an order starts preparing.", "اربط المكونات بصنف. يُخصم المخزون عند بدء تحضير الطلب.")} />
        <SelectField label={t("inventory.selectItem")} value={itemId} onChange={(event) => setItemId(event.target.value ? Number(event.target.value) : "")}>
          <option value="">—</option>
          {menuItems.map((item) => (
            <option key={item.item_id} value={item.item_id}>
              {pick(item.item_name, item.item_name_ar)}
            </option>
          ))}
        </SelectField>
        {itemId ? (
          <div className="mt-4 space-y-2.5">
            {lines.map((line, index) => {
              const ingredient = ingredients.find((row) => row.ingredient_id === line.ingredient_id);
              return (
                <div key={`${line.ingredient_id}-${index}`} className="rounded-xl border border-ink-100 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-ink-800">{ingredient ? pick(ingredient.ingredient_name, ingredient.ingredient_name_ar) : line.ingredient_id}</p>
                    <button className="text-ink-400 hover:text-rose-600" onClick={() => setLines((prev) => prev.filter((_, i) => i !== index))}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <TextField
                      label={t("common.quantity")}
                      type="number"
                      min={0.01}
                      step="0.01"
                      value={line.quantity}
                      onChange={(event) => setLines((prev) => prev.map((row, i) => (i === index ? { ...row, quantity: event.target.value } : row)))}
                    />
                    <TextField
                      label={t("inventory.unit")}
                      value={line.unit_of_measure}
                      onChange={(event) => setLines((prev) => prev.map((row, i) => (i === index ? { ...row, unit_of_measure: event.target.value } : row)))}
                    />
                  </div>
                </div>
              );
            })}
            <SelectField
              label={t("inventory.addLine")}
              value=""
              onChange={(event) => {
                const ingredient = ingredients.find((row) => row.ingredient_id === Number(event.target.value));
                if (!ingredient) return;
                setLines((prev) => [
                  ...prev,
                  { ingredient_id: ingredient.ingredient_id, quantity: "1", unit_of_measure: ingredient.unit_of_measure, notes: "" }
                ]);
              }}
            >
              <option value="">—</option>
              {ingredients
                .filter((ingredient) => !lines.some((line) => line.ingredient_id === ingredient.ingredient_id))
                .map((ingredient) => (
                  <option key={ingredient.ingredient_id} value={ingredient.ingredient_id}>
                    {pick(ingredient.ingredient_name, ingredient.ingredient_name_ar)} ({ingredient.unit_of_measure})
                  </option>
                ))}
            </SelectField>
            <Button className="w-full" loading={save.isPending} disabled={!itemId} onClick={() => save.mutate()}>
              {t("common.save")}
            </Button>
          </div>
        ) : (
          <p className="mt-4 text-sm text-ink-400">{pick("Select a menu item to view or edit its recipe.", "اختر صنفاً لعرض أو تعديل وصفته.")}</p>
        )}
      </Card>

      <Card className="card-pad">
        <SectionTitle title={itemId ? pick("Recipe lines", "سطور الوصفة") : t("inventory.recipes")} />
        {!itemId ? (
          <EmptyState title={pick("Choose an item", "اختر صنفاً")} />
        ) : recipe.isLoading ? (
          <Loading />
        ) : !lines.length ? (
          <EmptyState title={t("inventory.noRecipe")} description={pick("Add the first ingredient from the panel.", "أضف أول مكون من اللوحة الجانبية.")} />
        ) : (
          <div className="space-y-3">
            {lines.map((line, index) => {
              const ingredient = ingredients.find((row) => row.ingredient_id === line.ingredient_id);
              return (
                <div key={`${line.ingredient_id}-${index}`} className="flex items-center gap-3 rounded-xl bg-ink-50 px-4 py-3">
                  <span className="grid h-9 w-9 place-items-center rounded-lg bg-white text-brand-700"><Scale className="h-4 w-4" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-ink-900">{ingredient ? pick(ingredient.ingredient_name, ingredient.ingredient_name_ar) : line.ingredient_id}</p>
                    <p className="text-xs text-ink-400">{ingredient?.stock_status ? <StatusBadge status={ingredient.stock_status} /> : null}</p>
                  </div>
                  <p className="text-sm font-bold text-ink-800">{line.quantity} {line.unit_of_measure}</p>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
