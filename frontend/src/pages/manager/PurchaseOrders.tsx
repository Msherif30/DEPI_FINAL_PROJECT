import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, PackageCheck, PackageOpen, Plus, RefreshCw, Trash2, Truck } from "lucide-react";
import { useState } from "react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Loading,
  Modal,
  PageHeader,
  SelectField,
  StatusBadge,
  TextAreaField,
  TextField,
  useToast
} from "../../components/ui";
import { api, errorMessage, qs } from "../../lib/api";
import { dateTime, money, number } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { Ingredient, Paginated, PurchaseOrder, Supplier } from "../../lib/types";

interface LineDraft {
  ingredient_id: number | "";
  quantity_ordered: string;
  unit_cost: string;
}

const emptyLine = (): LineDraft => ({ ingredient_id: "", quantity_ordered: "1", unit_cost: "" });

export default function PurchaseOrders() {
  const { t, pick } = useI18n();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [receiving, setReceiving] = useState<PurchaseOrder | null>(null);
  const [supplierId, setSupplierId] = useState<number | "">("");
  const [expectedDate, setExpectedDate] = useState("");
  const [notes, setNotes] = useState("");
  const [submit, setSubmit] = useState(true);
  const [lines, setLines] = useState<LineDraft[]>([emptyLine()]);
  const [receipts, setReceipts] = useState<Record<number, string>>({});

  const orders = useQuery({
    queryKey: ["purchase-orders"],
    queryFn: () => api<Paginated<PurchaseOrder>>("/purchase-orders?page=1&page_size=100")
  });
  const suppliers = useQuery({ queryKey: ["suppliers"], queryFn: () => api<Supplier[]>("/suppliers") });
  const ingredients = useQuery({ queryKey: ["inventory"], queryFn: () => api<Ingredient[]>("/inventory") });

  const reset = () => {
    setSupplierId("");
    setExpectedDate("");
    setNotes("");
    setSubmit(true);
    setLines([emptyLine()]);
  };

  const create = useMutation({
    mutationFn: () =>
      api<PurchaseOrder>("/purchase-orders", {
        method: "POST",
        body: {
          supplier_id: supplierId,
          expected_date: expectedDate || undefined,
          notes: notes || undefined,
          submit,
          items: lines
            .filter((line) => line.ingredient_id !== "")
            .map((line) => ({
              ingredient_id: Number(line.ingredient_id),
              quantity_ordered: Number(line.quantity_ordered),
              unit_cost: line.unit_cost ? Number(line.unit_cost) : undefined
            }))
        }
      }),
    onSuccess: () => {
      toast.success(pick("Purchase order created", "تم إنشاء أمر الشراء"));
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      setCreateOpen(false);
      reset();
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const receive = useMutation({
    mutationFn: () =>
      api<PurchaseOrder>(`/purchase-orders/${receiving?.purchase_order_id}`, {
        method: "PATCH",
        body: {
          items: (receiving?.items ?? []).map((line) => ({
            purchase_order_item_id: line.purchase_order_item_id,
            quantity: Number(receipts[line.purchase_order_item_id] ?? 0)
          }))
        }
      }),
    onSuccess: () => {
      toast.success(pick("Stock received", "تم استلام المخزون"));
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["low-stock"] });
      queryClient.invalidateQueries({ queryKey: ["movements"] });
      setReceiving(null);
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const openReceive = (order: PurchaseOrder) => {
    setReceiving(order);
    const initial: Record<number, string> = {};
    for (const line of order.items) {
      initial[line.purchase_order_item_id] = String(Math.max(0, line.quantity_ordered - line.quantity_received));
    }
    setReceipts(initial);
  };

  const totalPreview = lines.reduce((sum, line) => sum + Number(line.quantity_ordered || 0) * Number(line.unit_cost || 0), 0);

  return (
    <div>
      <PageHeader
        eyebrow={pick("Manager", "الإدارة")}
        title={t("purchasing.title")}
        subtitle={t("purchasing.subtitle")}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => void orders.refetch()} loading={orders.isFetching}>
              <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> {t("purchasing.create")}
            </Button>
          </div>
        }
      />

      {orders.isLoading ? (
        <Loading />
      ) : !orders.data?.items.length ? (
        <EmptyState
          title={t("purchasing.empty")}
          icon={<PackageOpen className="h-6 w-6" />}
          action={<Button onClick={() => setCreateOpen(true)}><Plus className="h-4 w-4" /> {t("purchasing.create")}</Button>}
        />
      ) : (
        <div className="space-y-4">
          {orders.data.items.map((order) => (
            <Card key={order.purchase_order_id} className="overflow-hidden">
              <div className="flex flex-col gap-3 border-b border-ink-100 p-5 sm:flex-row sm:items-center">
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-50 text-brand-700"><Truck className="h-5 w-5" /></span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-display text-base font-extrabold text-ink-900">PO #{order.purchase_order_id}</p>
                      <StatusBadge status={order.status} />
                    </div>
                    <p className="text-sm text-ink-500">{order.supplier_name}</p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-4 text-sm">
                  <span className="inline-flex items-center gap-1.5 text-ink-500"><CalendarDays className="h-4 w-4" /> {order.expected_date ?? dateTime(order.order_date)}</span>
                  <span className="font-display text-base font-extrabold text-ink-900">{money(order.total_amount)}</span>
                  {order.status !== "received" ? (
                    <Button size="sm" onClick={() => openReceive(order)}>
                      <PackageCheck className="h-3.5 w-3.5" /> {t("purchasing.receive")}
                    </Button>
                  ) : null}
                </div>
              </div>
              <div className="table-wrap">
                <table className="data-table min-w-[520px]">
                  <thead>
                    <tr>
                      <th>{t("common.name")}</th>
                      <th>{t("purchasing.quantityOrdered")}</th>
                      <th>{t("purchasing.quantityReceived")}</th>
                      <th>{t("inventory.cost")}</th>
                      <th>{t("common.total")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.items.map((line) => (
                      <tr key={line.purchase_order_item_id}>
                        <td className="font-semibold text-ink-900">{line.ingredient_name}</td>
                        <td>{number(line.quantity_ordered, 2)} {line.unit_of_measure}</td>
                        <td>{number(line.quantity_received, 2)}</td>
                        <td>{line.unit_cost ? money(line.unit_cost) : "—"}</td>
                        <td className="font-semibold">{line.unit_cost ? money(line.unit_cost * line.quantity_ordered) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {order.notes ? <p className="border-t border-ink-100 bg-ink-50/50 px-5 py-2.5 text-xs text-ink-500">{order.notes}</p> : null}
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title={t("purchasing.create")}
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>{t("common.cancel")}</Button>
            <Button loading={create.isPending} disabled={!supplierId || !lines.some((line) => line.ingredient_id !== "")} onClick={() => create.mutate()}>
              {submit ? t("purchasing.submit") : t("common.save")}
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField label={t("purchasing.supplier")} value={supplierId} onChange={(event) => setSupplierId(event.target.value ? Number(event.target.value) : "")}>
            <option value="">—</option>
            {(suppliers.data ?? []).filter((supplier) => supplier.is_active).map((supplier) => (
              <option key={supplier.supplier_id} value={supplier.supplier_id}>{supplier.supplier_name}</option>
            ))}
          </SelectField>
          <TextField label={t("purchasing.expected")} type="date" value={expectedDate} onChange={(event) => setExpectedDate(event.target.value)} />
        </div>

        <div className="mt-5">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-bold text-ink-800">{t("purchasing.lines")}</p>
            <Button size="sm" variant="secondary" onClick={() => setLines((prev) => [...prev, emptyLine()])}>
              <Plus className="h-3.5 w-3.5" /> {t("purchasing.addLine")}
            </Button>
          </div>
          <div className="space-y-2">
            {lines.map((line, index) => (
              <div key={index} className="grid gap-2 rounded-xl border border-ink-100 p-2.5 sm:grid-cols-[1.5fr_0.7fr_0.8fr_auto]">
                <SelectField
                  label={index === 0 ? t("common.name") : undefined}
                  value={line.ingredient_id}
                  onChange={(event) =>
                    setLines((prev) => prev.map((row, i) => (i === index ? { ...row, ingredient_id: event.target.value ? Number(event.target.value) : "" } : row)))
                  }
                >
                  <option value="">—</option>
                  {(ingredients.data ?? []).map((ingredient) => (
                    <option key={ingredient.ingredient_id} value={ingredient.ingredient_id}>
                      {ingredient.ingredient_name} ({ingredient.unit_of_measure})
                    </option>
                  ))}
                </SelectField>
                <TextField
                  label={index === 0 ? t("common.quantity") : undefined}
                  type="number"
                  min={0.01}
                  step="0.01"
                  value={line.quantity_ordered}
                  onChange={(event) => setLines((prev) => prev.map((row, i) => (i === index ? { ...row, quantity_ordered: event.target.value } : row)))}
                />
                <TextField
                  label={index === 0 ? t("inventory.cost") : undefined}
                  type="number"
                  min={0}
                  step="0.01"
                  value={line.unit_cost}
                  onChange={(event) => setLines((prev) => prev.map((row, i) => (i === index ? { ...row, unit_cost: event.target.value } : row)))}
                />
                <div className={index === 0 ? "flex items-end pb-1" : "flex items-center"}>
                  <Button variant="ghost" size="icon" className="text-rose-500" disabled={lines.length === 1} onClick={() => setLines((prev) => prev.filter((_, i) => i !== index))}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <TextAreaField label={t("common.notes")} value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={1000} />
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-xl bg-ink-50 px-3.5 py-3">
              <span className="text-sm font-semibold text-ink-600">{t("common.total")}</span>
              <span className="font-display text-lg font-extrabold text-ink-900">{money(totalPreview)}</span>
            </div>
            <label className="flex items-center gap-2 text-sm font-semibold text-ink-700">
              <input type="checkbox" checked={submit} onChange={(event) => setSubmit(event.target.checked)} className="h-4 w-4 rounded border-ink-300 text-brand-600" />
              {t("purchasing.submit")}
            </label>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(receiving)}
        onClose={() => setReceiving(null)}
        title={`${t("purchasing.receiveTitle")} · PO #${receiving?.purchase_order_id ?? ""}`}
        description={receiving?.supplier_name ?? undefined}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setReceiving(null)}>{t("common.cancel")}</Button>
            <Button loading={receive.isPending} onClick={() => receive.mutate()}>{t("purchasing.receive")}</Button>
          </>
        }
      >
        <div className="space-y-3">
          {(receiving?.items ?? []).map((line) => {
            const remaining = Math.max(0, line.quantity_ordered - line.quantity_received);
            return (
              <div key={line.purchase_order_item_id} className="grid items-end gap-3 rounded-xl border border-ink-100 p-3 sm:grid-cols-[1fr_140px]">
                <div>
                  <p className="text-sm font-semibold text-ink-900">{line.ingredient_name}</p>
                  <p className="text-xs text-ink-500">
                    {t("purchasing.quantityOrdered")}: {number(line.quantity_ordered, 2)} · {t("purchasing.quantityReceived")}: {number(line.quantity_received, 2)} · {pick("Remaining", "المتبقي")}: {number(remaining, 2)} {line.unit_of_measure}
                  </p>
                </div>
                <TextField
                  label={pick("Receive now", "استلام الآن")}
                  type="number"
                  min={0}
                  max={remaining}
                  step="0.01"
                  value={receipts[line.purchase_order_item_id] ?? ""}
                  onChange={(event) => setReceipts((prev) => ({ ...prev, [line.purchase_order_item_id]: event.target.value }))}
                />
              </div>
            );
          })}
          <p className="rounded-xl bg-amber-50 px-3.5 py-2.5 text-xs text-amber-800">
            {pick(
              "Received quantities increase stock and are recorded as purchase movements with your user ID.",
              "الكميات المستلمة تزيد المخزون وتُسجل كحركات شراء باسم المستخدم."
            )}
          </p>
        </div>
      </Modal>
    </div>
  );
}
