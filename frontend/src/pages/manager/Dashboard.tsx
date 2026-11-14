import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  ArrowDownRight,
  ArrowUpRight,
  Banknote,
  Bot,
  ChefHat,
  CircleDollarSign,
  Clock3,
  Crown,
  Lightbulb,
  RefreshCw,
  Send,
  ShoppingBag,
  Sparkles,
  TrendingUp,
  XCircle
} from "lucide-react";
import { useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { Button, Card, EmptyState, Loading, PageHeader, SectionTitle, SelectField, StatCard, useToast } from "../../components/ui";
import { api, errorMessage, qs } from "../../lib/api";
import { daysAgo, money, number } from "../../lib/format";
import { useI18n } from "../../lib/i18n";

interface Overview {
  period: { start: string; end: string };
  total_revenue: number;
  paid_revenue: number;
  total_orders: number;
  completed_orders: number;
  cancelled_orders: number;
  pending_orders: number;
  average_order_value: number;
  best_selling_product: { item_name: string; item_name_ar?: string; quantity: number; revenue: number } | null;
  revenue_definition: string;
}

interface SalesPoint {
  bucket: string;
  revenue: number;
  orders: number;
  completed: number;
}

interface ProductRow {
  item_id: number;
  item_name: string;
  item_name_ar?: string;
  category: string;
  quantity: number;
  revenue: number;
  orders: number;
}

interface CategoryRow {
  category_id: number;
  category_name: string;
  category_name_ar?: string;
  quantity: number;
  revenue: number;
}

interface HourRow {
  hour: number;
  label: string;
  orders: number;
  revenue: number;
}

interface SourceRow {
  source: string;
  orders: number;
}

interface Insights {
  period: { start: string; end: string };
  revenue_change_percent: number;
  previous_period_revenue: number;
  peak_hour: HourRow | null;
  top_product: ProductRow | null;
  lowest_product: ProductRow | null;
  facts: string[];
  data_note: string;
}

const PIE_COLORS = ["#f98307", "#1f1f1d", "#0ea5e9", "#10b981", "#8b5cf6", "#f43f5e", "#eab308", "#64748b"];

export function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { name?: string; value?: number; color?: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-ink-100 bg-white px-3 py-2 text-xs shadow-lg">
      {label ? <p className="mb-1 font-bold text-ink-800">{label}</p> : null}
      {payload.map((entry, index) => (
        <p key={index} className="flex items-center gap-1.5 text-ink-600">
          <span className="h-2 w-2 rounded-full" style={{ background: entry.color }} />
          <span className="capitalize">{entry.name}</span>: <span className="font-bold">{Number(entry.value).toLocaleString()}</span>
        </p>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { t, pick } = useI18n();
  const toast = useToast();
  const [range, setRange] = useState("30");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  const start = daysAgo(Number(range) - 1);
  const filters = qs({ start, end: daysAgo(0) });
  const filterArgs = { start, end: daysAgo(0) };

  const overview = useQuery({ queryKey: ["analytics-overview", start], queryFn: () => api<Overview>(`/analytics/overview${filters}`) });
  const sales = useQuery({ queryKey: ["analytics-sales", start], queryFn: () => api<SalesPoint[]>(`/analytics/sales${filters}`) });
  const categories = useQuery({ queryKey: ["analytics-categories", start], queryFn: () => api<CategoryRow[]>(`/analytics/categories${filters}`) });
  const hours = useQuery({ queryKey: ["analytics-hours", start], queryFn: () => api<HourRow[]>(`/analytics/peak-hours${filters}`) });
  const sources = useQuery({ queryKey: ["analytics-sources", start], queryFn: () => api<SourceRow[]>(`/analytics/sources${filters}`) });
  const products = useQuery({ queryKey: ["analytics-products", start], queryFn: () => api<ProductRow[]>(`/analytics/products${filters}&limit=8`) });
  const insights = useQuery({ queryKey: ["analytics-insights", start], queryFn: () => api<Insights>(`/analytics/insights${filters}`) });

  const analyst = useMutation({
    mutationFn: () => api<{ answer: string; facts: string[]; data_note: string }>("/ai/analyst", { method: "POST", body: { question } }),
    onSuccess: (data) => setAnswer(data.answer),
    onError: (err) => toast.error(errorMessage(err))
  });

  const refreshAll = () => {
    void overview.refetch();
    void sales.refetch();
    void categories.refetch();
    void hours.refetch();
    void sources.refetch();
    void products.refetch();
    void insights.refetch();
  };

  const change = insights.data?.revenue_change_percent ?? 0;
  const peakHour = insights.data?.peak_hour;

  return (
    <div>
      <PageHeader
        eyebrow={pick("Manager", "الإدارة")}
        title={t("dashboard.title")}
        subtitle={t("dashboard.subtitle")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <SelectField value={range} onChange={(event) => setRange(event.target.value)} className="h-10 w-36">
              <option value="7">{pick("Last 7 days", "آخر ٧ أيام")}</option>
              <option value="30">{pick("Last 30 days", "آخر ٣٠ يوم")}</option>
              <option value="90">{pick("Last 90 days", "آخر ٩٠ يوم")}</option>
            </SelectField>
            <Button variant="secondary" onClick={refreshAll} loading={overview.isFetching}>
              <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
            </Button>
          </div>
        }
      />

      {overview.isLoading ? (
        <Loading />
      ) : overview.isError ? (
        <EmptyState title={t("error.generic")} description={errorMessage(overview.error)} action={<Button onClick={refreshAll}>{t("common.retry")}</Button>} />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label={t("dashboard.revenue")}
              value={money(overview.data?.total_revenue)}
              hint={overview.data?.revenue_definition}
              icon={<CircleDollarSign className="h-5 w-5" />}
              tone="brand"
            />
            <StatCard
              label={t("dashboard.paidRevenue")}
              value={money(overview.data?.paid_revenue)}
              hint={pick("Recorded payments only", "الدفعات المسجلة فقط")}
              icon={<Banknote className="h-5 w-5" />}
              tone="success"
            />
            <StatCard
              label={t("dashboard.completedOrders")}
              value={number(overview.data?.completed_orders)}
              hint={`${number(overview.data?.total_orders)} ${pick("total orders", "إجمالي الطلبات")}`}
              icon={<ShoppingBag className="h-5 w-5" />}
            />
            <StatCard
              label={t("dashboard.avgOrder")}
              value={money(overview.data?.average_order_value)}
              hint={change >= 0 ? `+${change.toFixed(1)}% ${pick("vs previous period", "مقارنة بالفترة السابقة")}` : `${change.toFixed(1)}% ${pick("vs previous period", "مقارنة بالفترة السابقة")}`}
              icon={change >= 0 ? <ArrowUpRight className="h-5 w-5" /> : <ArrowDownRight className="h-5 w-5" />}
              tone={change >= 0 ? "success" : "danger"}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <Card className="card-pad">
              <SectionTitle
                title={t("dashboard.sales")}
                description={`${overview.data?.period.start} → ${overview.data?.period.end}`}
                action={<span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-700"><TrendingUp className="h-3.5 w-3.5" /> {pick("completed only", "المكتمل فقط")}</span>}
              />
              <div className="h-72">
                {sales.data?.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={sales.data} margin={{ top: 5, right: 8, left: -18, bottom: 0 }}>
                      <defs>
                        <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#f98307" stopOpacity={0.45} />
                          <stop offset="100%" stopColor="#f98307" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e7e7e4" vertical={false} />
                      <XAxis dataKey="bucket" tick={{ fontSize: 10, fill: "#85857c" }} tickLine={false} axisLine={false} minTickGap={24} />
                      <YAxis tick={{ fontSize: 10, fill: "#85857c" }} tickLine={false} axisLine={false} />
                      <Tooltip content={<ChartTooltip />} />
                      <Area type="monotone" dataKey="revenue" name="Revenue" stroke="#f98307" strokeWidth={2.5} fill="url(#rev)" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState title={t("common.noData")} />
                )}
              </div>
            </Card>

            <Card className="card-pad">
              <SectionTitle title={t("dashboard.categories")} description={pick("Revenue share", "حصة الإيراد")} />
              <div className="h-56">
                {categories.data?.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={categories.data} dataKey="revenue" nameKey="category_name" cx="50%" cy="50%" innerRadius={52} outerRadius={82} paddingAngle={2}>
                        {categories.data.map((entry, index) => (
                          <Cell key={entry.category_id} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip content={<ChartTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState title={t("common.noData")} />
                )}
              </div>
              <div className="mt-2 space-y-1.5">
                {(categories.data ?? []).slice(0, 5).map((row, index) => (
                  <div key={row.category_id} className="flex items-center gap-2 text-xs">
                    <span className="h-2 w-2 rounded-full" style={{ background: PIE_COLORS[index % PIE_COLORS.length] }} />
                    <span className="min-w-0 flex-1 truncate text-ink-600">{pick(row.category_name, row.category_name_ar)}</span>
                    <span className="font-bold text-ink-800">{money(row.revenue)}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card className="card-pad xl:col-span-2">
              <SectionTitle
                title={t("dashboard.peakHours")}
                description={peakHour ? `${pick("Busiest hour", "أكثر ساعة ازدحاماً")}: ${peakHour.label} · ${peakHour.orders} ${pick("orders", "طلب")}` : undefined}
              />
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={hours.data ?? []} margin={{ top: 5, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e7e7e4" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 9, fill: "#85857c" }} tickLine={false} axisLine={false} interval={2} />
                    <YAxis tick={{ fontSize: 10, fill: "#85857c" }} tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="orders" name="Orders" radius={[4, 4, 0, 0]}>
                      {(hours.data ?? []).map((row) => (
                        <Cell key={row.hour} fill={peakHour && row.hour === peakHour.hour ? "#f98307" : "#d0d0ca"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card className="card-pad">
              <SectionTitle title={t("dashboard.sources")} />
              <div className="space-y-4">
                {(sources.data ?? []).map((row) => {
                  const max = Math.max(...(sources.data ?? []).map((item) => item.orders), 1);
                  return (
                    <div key={row.source}>
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <span className="font-semibold capitalize text-ink-700">{row.source.replaceAll("_", " ")}</span>
                        <span className="font-bold text-ink-500">{row.orders}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-ink-100">
                        <div className="h-full rounded-full bg-brand-500" style={{ width: `${(row.orders / max) * 100}%` }} />
                      </div>
                    </div>
                  );
                })}
                {!sources.data?.length ? <p className="text-sm text-ink-400">{t("common.noData")}</p> : null}
              </div>
              <div className="mt-5 rounded-xl bg-ink-50 p-3">
                <p className="flex items-center gap-1.5 text-xs font-bold text-ink-700"><Crown className="h-3.5 w-3.5 text-amber-500" /> {t("dashboard.bestSeller")}</p>
                <p className="mt-1 text-sm font-semibold text-ink-900">
                  {overview.data?.best_selling_product ? pick(overview.data.best_selling_product.item_name, overview.data.best_selling_product.item_name_ar) : "—"}
                </p>
                {overview.data?.best_selling_product ? (
                  <p className="text-xs text-ink-500">
                    {overview.data.best_selling_product.quantity} {pick("units", "وحدة")} · {money(overview.data.best_selling_product.revenue)}
                  </p>
                ) : null}
              </div>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
            <Card className="overflow-hidden">
              <div className="border-b border-ink-100 px-5 py-4">
                <h2 className="font-display text-base font-bold text-ink-900">{t("dashboard.topProducts")}</h2>
              </div>
              <div className="table-wrap">
                <table className="data-table min-w-[520px]">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>{t("common.name")}</th>
                      <th>{t("menuAdmin.category")}</th>
                      <th>{t("common.quantity")}</th>
                      <th>{t("dashboard.revenue")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(products.data ?? []).map((row, index) => (
                      <tr key={row.item_id}>
                        <td className="text-ink-400">{index + 1}</td>
                        <td className="font-semibold text-ink-900">{pick(row.item_name, row.item_name_ar)}</td>
                        <td className="text-ink-500">{row.category}</td>
                        <td>{number(row.quantity)}</td>
                        <td className="font-semibold text-ink-800">{money(row.revenue)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <div className="space-y-6">
              <Card className="card-pad">
                <SectionTitle title={t("dashboard.insights")} />
                <div className="space-y-2.5">
                  {(insights.data?.facts ?? []).map((fact) => (
                    <p key={fact} className="flex gap-2 text-xs leading-relaxed text-ink-600">
                      <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" /> {fact}
                    </p>
                  ))}
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <div className="rounded-xl bg-rose-50 px-3 py-2.5">
                    <p className="text-[10px] font-bold uppercase text-rose-500">{t("dashboard.cancelled")}</p>
                    <p className="font-display text-xl font-extrabold text-rose-800">{overview.data?.cancelled_orders ?? 0}</p>
                  </div>
                  <div className="rounded-xl bg-amber-50 px-3 py-2.5">
                    <p className="text-[10px] font-bold uppercase text-amber-600">{t("board.pending")}</p>
                    <p className="font-display text-xl font-extrabold text-amber-800">{overview.data?.pending_orders ?? 0}</p>
                  </div>
                </div>
                <p className="mt-3 text-[10px] leading-relaxed text-ink-400">{insights.data?.data_note}</p>
              </Card>

              <Card className="card-pad">
                <SectionTitle title={t("dashboard.analyst")} description={t("dashboard.analystHint")} />
                <div className="flex gap-2">
                  <input
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder={t("dashboard.analystPlaceholder")}
                    className="field"
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && question.trim()) analyst.mutate();
                    }}
                  />
                  <Button size="icon" onClick={() => analyst.mutate()} loading={analyst.isPending} disabled={!question.trim()}>
                    <Send className="h-4 w-4" />
                  </Button>
                </div>
                {answer ? (
                  <div className="mt-3 whitespace-pre-line rounded-xl bg-ink-900 p-3.5 text-xs leading-relaxed text-white/80">
                    <p className="mb-1.5 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-brand-300">
                      <Bot className="h-3.5 w-3.5" /> {pick("Grounded in MySQL", "مبني على بيانات MySQL")}
                    </p>
                    {answer}
                  </div>
                ) : null}
              </Card>
            </div>
          </div>

          <p className="flex items-center justify-center gap-1.5 text-center text-[11px] text-ink-400">
            <Clock3 className="h-3.5 w-3.5" /> {t("dashboard.revenueDefinition")}
          </p>
        </div>
      )}
    </div>
  );
}
