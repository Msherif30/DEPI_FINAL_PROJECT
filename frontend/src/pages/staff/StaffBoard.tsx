import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Banknote,
  BellRing,
  ChefHat,
  Check,
  CirclePlay,
  Clock3,
  RefreshCw,
  ShoppingBag,
  Utensils,
  Wifi,
  WifiOff,
  X
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge, Button, Card, ConfirmDialog, EmptyState, Loading, PageHeader, StatusBadge, useToast } from "../../components/ui";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dateTime, money } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { Order, OrderStatus, Paginated } from "../../lib/types";

interface Summary {
  counts: Record<OrderStatus, number>;
  total: number;
  latest_order_at?: string | null;
  role: string;
}

const columns: { status: OrderStatus; icon: React.ReactNode; tone: string }[] = [
  { status: "pending", icon: <Clock3 className="h-4 w-4" />, tone: "border-amber-300" },
  { status: "confirmed", icon: <ShoppingBag className="h-4 w-4" />, tone: "border-sky-300" },
  { status: "preparing", icon: <ChefHat className="h-4 w-4" />, tone: "border-violet-300" },
  { status: "completed", icon: <Check className="h-4 w-4" />, tone: "border-emerald-300" }
];

export default function StaffBoard() {
  const { t, pick } = useI18n();
  const { user, token } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [live, setLive] = useState(false);
  const [cancelId, setCancelId] = useState<number | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const orders = useQuery({
    queryKey: ["staff-orders"],
    queryFn: () => api<Paginated<Order>>("/staff/orders?page=1&page_size=150"),
    refetchInterval: 12_000
  });

  const summary = useQuery({
    queryKey: ["staff-summary"],
    queryFn: () => api<Summary>("/staff/orders/summary"),
    refetchInterval: 12_000
  });

  useEffect(() => {
    if (!token) return;
    let closed = false;
    let retry: number | undefined;

    const connect = () => {
      if (closed) return;
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const socket = new WebSocket(`${protocol}://${window.location.host}/ws/orders?token=${encodeURIComponent(token)}`);
      socketRef.current = socket;
      socket.onopen = () => setLive(true);
      socket.onclose = () => {
        setLive(false);
        if (!closed) retry = window.setTimeout(connect, 4000);
      };
      socket.onerror = () => setLive(false);
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as { type?: string; order?: Order };
          if (data.type === "order.created" && data.order) {
            toast.push(`${pick("New order", "طلب جديد")} #${data.order.order_id}`, "info");
            try {
              const ctx = new AudioContext();
              const oscillator = ctx.createOscillator();
              const gain = ctx.createGain();
              oscillator.connect(gain);
              gain.connect(ctx.destination);
              oscillator.frequency.value = 880;
              gain.gain.setValueAtTime(0.04, ctx.currentTime);
              gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25);
              oscillator.start();
              oscillator.stop(ctx.currentTime + 0.26);
            } catch {
              /* audio is a progressive enhancement */
            }
          }
          queryClient.invalidateQueries({ queryKey: ["staff-orders"] });
          queryClient.invalidateQueries({ queryKey: ["staff-summary"] });
        } catch {
          /* ignore malformed socket payloads */
        }
      };
    };

    connect();
    return () => {
      closed = true;
      if (retry) window.clearTimeout(retry);
      socketRef.current?.close();
    };
  }, [token, queryClient, toast, pick]);

  const statusMutation = useMutation({
    mutationFn: ({ orderId, status }: { orderId: number; status: OrderStatus }) =>
      api(`/orders/${orderId}/status`, { method: "PATCH", body: { status } }),
    onSuccess: () => {
      toast.success(t("board.updated"));
      queryClient.invalidateQueries({ queryKey: ["staff-orders"] });
      queryClient.invalidateQueries({ queryKey: ["staff-summary"] });
      setCancelId(null);
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const paymentMutation = useMutation({
    mutationFn: (orderId: number) =>
      api(`/orders/${orderId}/payment`, { method: "PATCH", body: { payment_status: "paid" } }),
    onSuccess: () => {
      toast.success(t("board.updated"));
      queryClient.invalidateQueries({ queryKey: ["staff-orders"] });
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const can = (previous: OrderStatus, next: OrderStatus) => {
    const role = user?.role;
    if (role === "manager") return true;
    if (role === "cashier") return ["pending->confirmed", "pending->cancelled", "confirmed->cancelled"].includes(`${previous}->${next}`);
    if (role === "chef") return ["confirmed->preparing", "preparing->completed"].includes(`${previous}->${next}`);
    return false;
  };

  const items = orders.data?.items ?? [];
  const active = items.filter((order) => order.status !== "cancelled");

  return (
    <div>
      <PageHeader
        eyebrow={pick("Operations", "التشغيل")}
        title={t("board.title")}
        subtitle={t("board.subtitle")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={clsx(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-bold",
                live ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-ink-200 bg-white text-ink-500"
              )}
            >
              {live ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
              {live ? t("board.live") : t("board.offline")}
            </span>
            <Button variant="secondary" loading={orders.isFetching} onClick={() => {
              void orders.refetch();
              void summary.refetch();
            }}>
              <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
            </Button>
          </div>
        }
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {columns.map((column) => (
          <Card key={column.status} className={clsx("border-s-4 p-4", column.tone)}>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-ink-500">
                {column.icon} {t(`board.${column.status}`)}
              </span>
              <span className="font-display text-xl font-extrabold text-ink-900">{summary.data?.counts?.[column.status] ?? 0}</span>
            </div>
          </Card>
        ))}
      </div>

      {orders.isLoading ? (
        <Loading />
      ) : orders.isError ? (
        <EmptyState title={t("error.generic")} description={errorMessage(orders.error)} action={<Button onClick={() => void orders.refetch()}>{t("common.retry")}</Button>} />
      ) : (
        <div className="no-scrollbar -mx-1 flex gap-4 overflow-x-auto px-1 pb-4">
          {columns.map((column) => {
            const columnOrders = active
              .filter((order) => order.status === column.status)
              .sort((a, b) => +new Date(a.order_date) - +new Date(b.order_date));
            return (
              <div key={column.status} className="flex w-[320px] shrink-0 flex-col rounded-2xl bg-ink-100/60 p-2.5">
                <div className="mb-2 flex items-center justify-between px-1.5 py-1">
                  <span className="inline-flex items-center gap-2 text-sm font-bold text-ink-700">
                    {column.icon} {t(`board.${column.status}`)}
                  </span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-xs font-bold text-ink-500">{columnOrders.length}</span>
                </div>
                <div className="space-y-2.5">
                  {columnOrders.length ? (
                    columnOrders.map((order) => (
                      <OrderCard
                        key={order.order_id}
                        order={order}
                        can={can}
                        isStaff={user?.role === "cashier" || user?.role === "manager"}
                        busy={statusMutation.isPending || paymentMutation.isPending}
                        onStatus={(status) => statusMutation.mutate({ orderId: order.order_id, status })}
                        onCancel={() => setCancelId(order.order_id)}
                        onPaid={() => paymentMutation.mutate(order.order_id)}
                      />
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-ink-200 bg-white/60 px-3 py-8 text-center text-xs text-ink-400">
                      {t("board.noOrders")}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <ConfirmDialog
        open={cancelId !== null}
        title={t("board.cancel")}
        description={pick("Stock already consumed will be returned automatically.", "سيتم إرجاع المخزون المستهلك تلقائياً.")}
        confirmLabel={t("board.cancel")}
        danger
        onClose={() => setCancelId(null)}
        onConfirm={() => {
          if (cancelId !== null) statusMutation.mutate({ orderId: cancelId, status: "cancelled" });
        }}
      />
    </div>
  );
}

function OrderCard({
  order,
  can,
  isStaff,
  busy,
  onStatus,
  onCancel,
  onPaid
}: {
  order: Order;
  can: (previous: OrderStatus, next: OrderStatus) => boolean;
  isStaff: boolean;
  busy: boolean;
  onStatus: (status: OrderStatus) => void;
  onCancel: () => void;
  onPaid: () => void;
}) {
  const { t, pick } = useI18n();
  const ageMinutes = Math.max(0, Math.round((Date.now() - new Date(order.order_date).getTime()) / 60000));

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-ink-100 px-4 py-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-display text-sm font-extrabold text-ink-900">#{order.order_id}</p>
            <p className="text-[11px] text-ink-400">
              {order.customer_name || pick("Walk-in", "زائر")} · {order.order_source.replaceAll("_", " ")}
            </p>
          </div>
          <div className="text-end">
            <p className="font-display text-sm font-extrabold text-brand-700">{money(order.total_amount)}</p>
            <p className="text-[10px] text-ink-400">{ageMinutes} {t("common.min")}</p>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <StatusBadge status={order.payment_status} />
          {order.order_notes ? <Badge tone="warn">{pick("Notes", "ملاحظات")}</Badge> : null}
        </div>
      </div>

      <div className="space-y-1.5 px-4 py-3">
        {order.items.map((item) => (
          <div key={item.order_item_id} className="flex items-start justify-between gap-2 text-xs">
            <span className="min-w-0 text-ink-700">
              <span className="font-bold text-ink-900">{item.quantity}×</span> {item.item_name_snapshot ?? item.item_id}
            </span>
            <span className="shrink-0 text-ink-400">{money(item.line_total)}</span>
          </div>
        ))}
        {order.order_notes ? <p className="rounded-lg bg-amber-50 px-2 py-1.5 text-[11px] text-amber-800">{order.order_notes}</p> : null}
      </div>

      <div className="space-y-1.5 border-t border-ink-100 bg-ink-50/50 px-3 py-2.5">
        {order.status === "pending" && can("pending", "confirmed") ? (
          <Button size="sm" className="w-full" disabled={busy} onClick={() => onStatus("confirmed")}>
            <Check className="h-3.5 w-3.5" /> {t("board.confirmOrder")}
          </Button>
        ) : null}
        {order.status === "confirmed" && can("confirmed", "preparing") ? (
          <Button size="sm" className="w-full" disabled={busy} onClick={() => onStatus("preparing")}>
            <CirclePlay className="h-3.5 w-3.5" /> {t("board.startPreparing")}
          </Button>
        ) : null}
        {order.status === "preparing" && can("preparing", "completed") ? (
          <Button size="sm" variant="dark" className="w-full" disabled={busy} onClick={() => onStatus("completed")}>
            <Utensils className="h-3.5 w-3.5" /> {t("board.complete")}
          </Button>
        ) : null}
        <div className="flex gap-1.5">
          {isStaff && order.payment_status !== "paid" && order.status !== "cancelled" ? (
            <Button size="sm" variant="secondary" className="flex-1" disabled={busy} onClick={onPaid}>
              <Banknote className="h-3.5 w-3.5" /> {t("board.markPaid")}
            </Button>
          ) : null}
          {can(order.status, "cancelled") ? (
            <Button size="sm" variant="ghost" className="flex-1 text-rose-600 hover:bg-rose-50" disabled={busy} onClick={onCancel}>
              <X className="h-3.5 w-3.5" /> {t("board.cancel")}
            </Button>
          ) : null}
        </div>
        <p className="text-center text-[10px] text-ink-400">{dateTime(order.order_date)}</p>
      </div>
    </Card>
  );
}
