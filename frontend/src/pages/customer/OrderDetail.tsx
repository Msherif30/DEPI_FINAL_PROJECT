import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, Check, ChefHat, Circle, Clock3, CreditCard, MapPin, PackageCheck, ReceiptText, RotateCcw, ShoppingBag, XCircle } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Badge, Button, Card, EmptyState, Loading, PageHeader, StatusBadge } from "../../components/ui";
import { api, errorMessage } from "../../lib/api";
import { useCart } from "../../lib/cart";
import { dateTime, money } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { Order, OrderStatus } from "../../lib/types";

const steps: { key: OrderStatus; icon: React.ReactNode }[] = [
  { key: "pending", icon: <Clock3 className="h-4 w-4" /> },
  { key: "confirmed", icon: <ReceiptText className="h-4 w-4" /> },
  { key: "preparing", icon: <ChefHat className="h-4 w-4" /> },
  { key: "completed", icon: <PackageCheck className="h-4 w-4" /> }
];

export default function OrderDetail() {
  const { orderId: id } = useParams();
  const { t, pick } = useI18n();
  const cart = useCart();
  const navigate = useNavigate();

  const query = useQuery({
    queryKey: ["order", id],
    queryFn: () => api<Order>(`/orders/${id}`),
    enabled: Boolean(id),
    refetchInterval: (queryState) => {
      const status = queryState.state.data?.status;
      return status === "completed" || status === "cancelled" ? false : 8000;
    }
  });

  if (query.isLoading) return <Loading />;
  if (query.isError || !query.data) {
    return (
      <EmptyState
        title={t("orders.notFound")}
        description={query.isError ? errorMessage(query.error) : undefined}
        action={
          <Link to="/orders">
            <Button>{t("common.back")}</Button>
          </Link>
        }
      />
    );
  }

  const order = query.data;
  const cancelled = order.status === "cancelled";
  const activeIndex = cancelled ? -1 : steps.findIndex((step) => step.key === order.status);
  const currentIndex = order.status === "completed" ? steps.length - 1 : activeIndex;

  const reorder = () => {
    cart.clear();
    for (const item of order.items) {
      cart.add(
        {
          item_id: item.item_id,
          item_name: item.item_name_snapshot ?? `Item ${item.item_id}`,
          item_name_ar: item.item_name_ar,
          price: Number(item.unit_price)
        },
        item.quantity
      );
    }
    navigate("/menu");
  };

  return (
    <div>
      <Link to="/orders" className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-ink-500 hover:text-ink-800">
        <ArrowLeft className="h-4 w-4 rtl:rotate-180" /> {t("orders.title")}
      </Link>

      <PageHeader
        eyebrow={dateTime(order.order_date)}
        title={`${t("orders.order")} #${order.order_id}`}
        subtitle={`${order.items.length} ${t("common.items")} · ${order.order_source.replaceAll("_", " ")}`}
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge status={order.status} />
            <StatusBadge status={order.payment_status} />
            <Button variant="secondary" onClick={reorder}>
              <RotateCcw className="h-4 w-4" /> {pick("Order again", "اطلب مرة أخرى")}
            </Button>
          </div>
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Card className="card-pad">
            <h2 className="mb-5 font-display text-lg font-bold text-ink-900">{t("orders.timeline")}</h2>
            {cancelled ? (
              <div className="flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-800">
                <XCircle className="h-5 w-5" /> {pick("This order was cancelled.", "تم إلغاء هذا الطلب.")}
              </div>
            ) : (
              <div className="relative flex flex-col gap-0 sm:flex-row sm:justify-between">
                {steps.map((step, index) => {
                  const done = index <= currentIndex;
                  const current = index === currentIndex && order.status !== "completed";
                  return (
                    <div key={step.key} className="relative flex flex-1 items-start gap-3 pb-6 last:pb-0 sm:flex-col sm:items-center sm:gap-2 sm:pb-0 sm:text-center">
                      {index < steps.length - 1 ? (
                        <span
                          className={clsx(
                            "absolute start-4 top-9 h-[calc(100%-2.5rem)] w-0.5 sm:start-1/2 sm:top-4 sm:h-0.5 sm:w-full",
                            index < currentIndex ? "bg-brand-500" : "bg-ink-200"
                          )}
                        />
                      ) : null}
                      <span
                        className={clsx(
                          "relative z-10 grid h-9 w-9 shrink-0 place-items-center rounded-full border-2 transition",
                          done
                            ? "border-brand-500 bg-brand-500 text-white"
                            : "border-ink-200 bg-white text-ink-300",
                          current && "ring-4 ring-brand-100"
                        )}
                      >
                        {index < currentIndex ? <Check className="h-4 w-4" /> : step.icon}
                      </span>
                      <div>
                        <p className={clsx("text-sm font-bold capitalize", done ? "text-ink-900" : "text-ink-400")}>{t(`status.${step.key}`)}</p>
                        {step.key === order.status ? (
                          <p className="text-[11px] text-brand-700">{pick("Current status", "الحالة الحالية")}</p>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {order.status_history.length ? (
              <div className="mt-6 space-y-2 border-t border-ink-100 pt-4">
                {[...order.status_history].reverse().map((entry) => (
                  <div key={entry.history_id} className="flex items-center justify-between gap-3 text-xs">
                    <span className="inline-flex items-center gap-1.5 text-ink-600">
                      <Circle className="h-2 w-2 fill-current text-brand-400" />
                      <span className="font-semibold capitalize">{entry.new_status}</span>
                      {entry.changed_by_name ? <span className="text-ink-400">· {entry.changed_by_name}</span> : null}
                    </span>
                    <span className="text-ink-400">{dateTime(entry.changed_at)}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </Card>

          <Card className="overflow-hidden">
            <div className="border-b border-ink-100 px-5 py-4">
              <h2 className="font-display text-base font-bold text-ink-900">{t("orders.items")}</h2>
            </div>
            <div className="divide-y divide-ink-100">
              {order.items.map((item) => (
                <div key={item.order_item_id} className="flex items-center gap-4 px-5 py-3.5">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-ink-100 text-xs font-extrabold text-ink-600">{item.quantity}×</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-ink-900">{pick(item.item_name_snapshot, item.item_name_ar)}</p>
                    <p className="text-xs text-ink-400">{money(item.unit_price)}</p>
                    {item.special_instructions ? <p className="text-xs text-amber-700">{item.special_instructions}</p> : null}
                  </div>
                  <p className="text-sm font-bold text-ink-800">{money(item.line_total)}</p>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between border-t border-ink-100 bg-ink-50/60 px-5 py-4">
              <span className="text-sm font-bold text-ink-700">{t("common.total")}</span>
              <span className="font-display text-xl font-extrabold text-ink-900">{money(order.total_amount)}</span>
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="card-pad">
            <h2 className="mb-3 font-display text-base font-bold text-ink-900">{t("orders.payment")}</h2>
            <dl className="space-y-2.5 text-sm">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-500">{t("common.status")}</dt>
                <dd><StatusBadge status={order.payment_status} /></dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-500">{t("menu.paymentMethod")}</dt>
                <dd className="font-semibold capitalize text-ink-800">{order.payment_method?.replaceAll("_", " ") ?? "—"}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-500">{t("common.total")}</dt>
                <dd className="font-extrabold text-ink-900">{money(order.total_amount)}</dd>
              </div>
            </dl>
            {order.payments.length ? (
              <div className="mt-4 space-y-2 border-t border-ink-100 pt-3">
                {order.payments.map((payment) => (
                  <div key={payment.payment_id} className="flex items-center justify-between text-xs text-ink-500">
                    <span className="inline-flex items-center gap-1"><CreditCard className="h-3.5 w-3.5" /> {payment.payment_method}</span>
                    <span>{money(payment.amount)} · {payment.payment_status}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </Card>

          {order.order_notes ? (
            <Card className="card-pad">
              <h2 className="mb-2 font-display text-base font-bold text-ink-900">{t("menu.orderNotes")}</h2>
              <p className="text-sm leading-relaxed text-ink-600">{order.order_notes}</p>
            </Card>
          ) : null}

          <Card className="card-pad">
            <h2 className="mb-2 font-display text-base font-bold text-ink-900">{t("common.notes")}</h2>
            <div className="space-y-2 text-sm text-ink-500">
              <p className="inline-flex items-center gap-2"><MapPin className="h-4 w-4 text-ink-400" /> {order.order_source.replaceAll("_", " ")}</p>
              <p className="inline-flex items-center gap-2"><Clock3 className="h-4 w-4 text-ink-400" /> {dateTime(order.order_date)}</p>
            </div>
            {order.status !== "completed" && order.status !== "cancelled" ? (
              <Badge tone="info" className="mt-3">{pick("Live updates enabled", "التحديثات المباشرة مفعلة")}</Badge>
            ) : null}
          </Card>
        </div>
      </div>
    </div>
  );
}
