import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowRight, ClipboardList, Clock3, RefreshCw, ReceiptText, ShoppingBag } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, Card, EmptyState, Loading, PageHeader, StatusBadge } from "../../components/ui";
import { api, errorMessage } from "../../lib/api";
import { dateTime, money } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { Order, Paginated } from "../../lib/types";

export default function Orders() {
  const { t, pick } = useI18n();
  const query = useQuery({
    queryKey: ["my-orders"],
    queryFn: () => api<Paginated<Order>>("/orders?page=1&page_size=50"),
    refetchInterval: 15_000
  });

  return (
    <div>
      <PageHeader
        eyebrow={t("app.name")}
        title={t("orders.title")}
        subtitle={t("orders.subtitle")}
        actions={
          <Button variant="secondary" onClick={() => void query.refetch()} loading={query.isFetching}>
            <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
          </Button>
        }
      />

      {query.isLoading ? (
        <Loading />
      ) : query.isError ? (
        <EmptyState title={t("error.generic")} description={errorMessage(query.error)} action={<Button onClick={() => void query.refetch()}>{t("common.retry")}</Button>} />
      ) : !query.data?.items.length ? (
        <EmptyState
          title={t("orders.empty")}
          icon={<ClipboardList className="h-6 w-6" />}
          action={
            <Link to="/menu">
              <Button>
                <ShoppingBag className="h-4 w-4" /> {t("nav.menu")}
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="grid gap-4">
          {query.data.items.map((order) => (
            <Card key={order.order_id} className="overflow-hidden transition hover:shadow-lg">
              <Link to={`/orders/${order.order_id}`} className="block">
                <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
                  <div className="flex min-w-0 flex-1 items-center gap-4">
                    <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-brand-50 text-brand-700">
                      <ReceiptText className="h-6 w-6" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-display text-base font-extrabold text-ink-900">
                          {t("orders.order")} #{order.order_id}
                        </p>
                        <StatusBadge status={order.status} />
                        <StatusBadge status={order.payment_status} />
                      </div>
                      <p className="mt-1 truncate text-sm text-ink-500">
                        {order.items.map((item) => `${item.quantity}× ${item.item_name_snapshot ?? item.item_id}`).join(" · ")}
                      </p>
                      <p className="mt-1 inline-flex items-center gap-1 text-xs text-ink-400">
                        <Clock3 className="h-3.5 w-3.5" /> {dateTime(order.order_date)} · {order.order_source.replaceAll("_", " ")}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between gap-4 sm:flex-col sm:items-end">
                    <p className="font-display text-lg font-extrabold text-ink-900">{money(order.total_amount)}</p>
                    <span className="inline-flex items-center gap-1 text-xs font-bold text-brand-700">
                      {pick("Track order", "تتبع الطلب")} <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
                    </span>
                  </div>
                </div>
              </Link>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
