import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, BarChart3, BrainCircuit, CalendarRange, History, Sparkles, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Button, Card, EmptyState, Loading, PageHeader, SectionTitle, SelectField, StatCard, useToast } from "../../components/ui";
import { ChartTooltip } from "./Dashboard";
import { api, errorMessage, qs } from "../../lib/api";
import { dateTime, day, money, number } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { MenuItem, Paginated } from "../../lib/types";

interface Metrics {
  mae: number;
  rmse: number;
  baseline_mae: number;
  baseline_rmse: number;
  model_comparison: Record<string, { mae: number; rmse: number }>;
}

interface Performance {
  trained: boolean;
  metrics: Metrics | null;
  model_name: string | null;
  trained_at: string | null;
  data_range: { start: string | null; end: string | null };
  available_completed_days: number;
  available_completed_order_lines: number;
  warnings: string[];
}

interface Prediction {
  item_id: number;
  item_name: string;
  item_name_ar?: string | null;
  forecast_date: string;
  predicted_quantity: number;
}

interface PredictionsResponse {
  trained: boolean;
  model_name?: string;
  metrics?: Metrics | null;
  predictions: Prediction[];
  warnings?: string[];
  data_range?: { start?: string; end?: string };
  trained_at?: string;
  horizon_days?: number;
  disclaimer?: string;
  message?: string;
}

interface HistoryPoint {
  date: string;
  quantity: number;
}

export default function Forecast() {
  const { t, pick } = useI18n();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [horizon, setHorizon] = useState("7");
  const [itemId, setItemId] = useState<number | "">("");

  const performance = useQuery({ queryKey: ["forecast-performance"], queryFn: () => api<Performance>("/forecast/performance") });
  const predictions = useQuery({
    queryKey: ["forecast-predictions", horizon, itemId],
    queryFn: () => api<PredictionsResponse>(`/forecast/predictions${qs({ horizon_days: Number(horizon), item_id: itemId || undefined })}`)
  });
  const history = useQuery({ queryKey: ["forecast-history"], queryFn: () => api<{ series: HistoryPoint[] }>("/forecast/history?days=90") });
  const menu = useQuery({ queryKey: ["forecast-menu"], queryFn: () => api<Paginated<MenuItem>>("/menu?page=1&page_size=100&sort=name") });

  const train = useMutation({
    mutationFn: () => api<Performance>("/forecast/train", { method: "POST" }),
    onSuccess: () => {
      toast.success(pick("Model trained", "تم تدريب النموذج"));
      queryClient.invalidateQueries({ queryKey: ["forecast-performance"] });
      queryClient.invalidateQueries({ queryKey: ["forecast-predictions"] });
      queryClient.invalidateQueries({ queryKey: ["forecast-history"] });
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const grouped = useMemo(() => {
    const rows = predictions.data?.predictions ?? [];
    const map = new Map<number, { item_id: number; item_name: string; item_name_ar?: string | null; total: number; first?: string; last?: string; days: number }>();
    for (const row of rows) {
      const found = map.get(row.item_id) ?? { item_id: row.item_id, item_name: row.item_name, item_name_ar: row.item_name_ar, total: 0, days: 0 };
      found.total += Number(row.predicted_quantity);
      found.days += 1;
      if (!found.first || row.forecast_date < found.first) found.first = row.forecast_date;
      if (!found.last || row.forecast_date > found.last) found.last = row.forecast_date;
      map.set(row.item_id, found);
    }
    return [...map.values()].sort((a, b) => b.total - a.total);
  }, [predictions.data]);

  const meta = predictions.data ?? performance.data;
  const warnings = [...new Set([...(performance.data?.warnings ?? []), ...(predictions.data?.warnings ?? [])])];

  return (
    <div>
      <PageHeader
        eyebrow={pick("Manager", "الإدارة")}
        title={t("forecast.title")}
        subtitle={t("forecast.subtitle")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={() => void performance.refetch()} loading={performance.isFetching}>
              {t("common.refresh")}
            </Button>
            <Button onClick={() => train.mutate()} loading={train.isPending}>
              <BrainCircuit className="h-4 w-4" /> {performance.data?.trained ? t("forecast.retrain") : t("forecast.train")}
            </Button>
          </div>
        }
      />

      {performance.isLoading ? (
        <Loading />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label={t("forecast.model")}
              value={<span className="text-lg">{performance.data?.model_name ?? "—"}</span>}
              hint={performance.data?.trained ? `${t("forecast.trained")} ${dateTime(performance.data.trained_at)}` : t("forecast.notTrained")}
              icon={<Sparkles className="h-5 w-5" />}
              tone="brand"
            />
            <StatCard label={t("forecast.mae")} value={performance.data?.metrics?.mae?.toFixed(3) ?? "—"} hint={`${t("forecast.baseline")}: ${performance.data?.metrics?.baseline_mae?.toFixed(3) ?? "—"}`} icon={<TrendingUp className="h-5 w-5" />} tone="success" />
            <StatCard label={t("forecast.rmse")} value={performance.data?.metrics?.rmse?.toFixed(3) ?? "—"} hint={`${pick("Baseline", "خط الأساس")}: ${performance.data?.metrics?.baseline_rmse?.toFixed(3) ?? "—"}`} icon={<BarChart3 className="h-5 w-5" />} />
            <StatCard
              label={pick("Data coverage", "تغطية البيانات")}
              value={`${performance.data?.available_completed_days ?? 0} ${pick("days", "يوم")}`}
              hint={`${performance.data?.available_completed_order_lines ?? 0} ${pick("completed order lines", "سطر طلب مكتمل")}`}
              icon={<CalendarRange className="h-5 w-5" />}
              tone="warn"
            />
          </div>

          {warnings.length ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
              <p className="mb-2 inline-flex items-center gap-2 text-sm font-bold text-amber-900">
                <AlertTriangle className="h-4 w-4" /> {t("forecast.warnings")}
              </p>
              <ul className="space-y-1.5">
                {warnings.map((warning) => (
                  <li key={warning} className="text-xs leading-relaxed text-amber-800">• {warning}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
            <Card className="card-pad">
              <SectionTitle
                title={t("forecast.history")}
                description={performance.data?.data_range?.start ? `${performance.data.data_range.start} → ${performance.data.data_range.end}` : undefined}
                action={<Badge tone="info">{pick("completed only", "المكتمل فقط")}</Badge>}
              />
              <div className="h-64">
                {history.data?.series?.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={history.data.series} margin={{ top: 5, right: 8, left: -18, bottom: 0 }}>
                      <defs>
                        <linearGradient id="hist" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.4} />
                          <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e7e7e4" vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#85857c" }} tickLine={false} axisLine={false} minTickGap={28} tickFormatter={(value: string) => day(value)} />
                      <YAxis tick={{ fontSize: 10, fill: "#85857c" }} tickLine={false} axisLine={false} allowDecimals={false} />
                      <Tooltip content={<ChartTooltip />} />
                      <Area type="monotone" dataKey="quantity" name="Units" stroke="#0ea5e9" strokeWidth={2.5} fill="url(#hist)" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState title={t("common.noData")} />
                )}
              </div>
            </Card>

            <Card className="card-pad">
              <SectionTitle title={t("forecast.predictions")} />
              <div className="grid grid-cols-2 gap-3">
                <SelectField label={t("forecast.horizon")} value={horizon} onChange={(event) => setHorizon(event.target.value)}>
                  <option value="7">7</option>
                  <option value="14">14</option>
                  <option value="21">21</option>
                  <option value="30">30</option>
                </SelectField>
                <SelectField label={t("forecast.item")} value={itemId} onChange={(event) => setItemId(event.target.value ? Number(event.target.value) : "")}>
                  <option value="">{pick("All items", "كل الأصناف")}</option>
                  {(menu.data?.items ?? []).map((item) => (
                    <option key={item.item_id} value={item.item_id}>{pick(item.item_name, item.item_name_ar)}</option>
                  ))}
                </SelectField>
              </div>
              <div className="mt-4 space-y-2.5">
                {predictions.data?.trained ? (
                  grouped.slice(0, 6).map((row) => (
                    <div key={row.item_id} className="flex items-center justify-between gap-3 rounded-xl bg-ink-50 px-3 py-2.5">
                      <p className="min-w-0 truncate text-xs font-semibold text-ink-800">{pick(row.item_name, row.item_name_ar)}</p>
                      <p className="shrink-0 text-xs font-extrabold text-brand-700">{number(row.total, 1)} {pick("units", "وحدة")}</p>
                    </div>
                  ))
                ) : (
                  <p className="rounded-xl bg-ink-50 px-3 py-6 text-center text-xs text-ink-500">{t("forecast.empty")}</p>
                )}
              </div>
              {predictions.data?.trained ? (
                <p className="mt-4 text-[10px] leading-relaxed text-ink-400">
                  {predictions.data.disclaimer ?? t("forecast.disclaimer")}
                </p>
              ) : null}
            </Card>
          </div>

          <Card className="overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 px-5 py-4">
              <div>
                <h2 className="font-display text-base font-bold text-ink-900">{t("forecast.predictions")}</h2>
                <p className="text-xs text-ink-500">{horizon} {pick("days ahead", "يوم قادمة")} · {grouped.length} {pick("products", "صنف")}</p>
              </div>
              <Badge tone={predictions.data?.trained ? "success" : "neutral"}>
                {predictions.data?.trained ? (predictions.data.model_name ?? t("forecast.trained")) : t("forecast.notTrained")}
              </Badge>
            </div>
            {!predictions.data?.trained ? (
              <div className="p-5">
                <EmptyState
                  title={t("forecast.empty")}
                  description={predictions.data?.message}
                  icon={<History className="h-6 w-6" />}
                  action={<Button onClick={() => train.mutate()} loading={train.isPending}>{t("forecast.train")}</Button>}
                />
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>{t("forecast.item")}</th>
                      <th>{pick("Total forecast", "إجمالي التوقع")}</th>
                      <th>{pick("Daily average", "المتوسط اليومي")}</th>
                      <th>{pick("First day", "أول يوم")}</th>
                      <th>{pick("Last day", "آخر يوم")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {grouped.map((row, index) => (
                      <tr key={row.item_id}>
                        <td className="text-ink-400">{index + 1}</td>
                        <td className="font-semibold text-ink-900">{pick(row.item_name, row.item_name_ar)}</td>
                        <td className="font-bold text-brand-700">{number(row.total, 1)}</td>
                        <td>{number(row.total / Math.max(1, row.days), 2)}</td>
                        <td className="text-xs text-ink-500">{row.first ? day(row.first) : "—"}</td>
                        <td className="text-xs text-ink-500">{row.last ? day(row.last) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {performance.data?.metrics?.model_comparison ? (
            <Card className="card-pad">
              <SectionTitle title={pick("Holdout comparison", "مقارنة عينة الاختبار")} description={pick("Lower MAE is better. The baseline is a per-product mean.", "الخطأ الأقل أفضل. خط الأساس هو متوسط كل صنف.")} />
              <div className="grid gap-3 sm:grid-cols-3">
                {Object.entries(performance.data.metrics.model_comparison).map(([name, value]) => (
                  <div key={name} className={clsx("rounded-xl border p-3.5", name === performance.data?.model_name ? "border-brand-300 bg-brand-50" : "border-ink-100 bg-white")}>
                    <p className="text-xs font-bold text-ink-700">{name}</p>
                    <p className="mt-1 text-lg font-extrabold text-ink-900">MAE {value.mae.toFixed(3)}</p>
                    <p className="text-xs text-ink-500">RMSE {value.rmse.toFixed(3)}</p>
                  </div>
                ))}
                <div className={clsx("rounded-xl border p-3.5", performance.data.model_name === "PerProductMeanBaseline" ? "border-brand-300 bg-brand-50" : "border-ink-100 bg-white")}>
                  <p className="text-xs font-bold text-ink-700">Per-product baseline</p>
                  <p className="mt-1 text-lg font-extrabold text-ink-900">MAE {performance.data.metrics.baseline_mae.toFixed(3)}</p>
                  <p className="text-xs text-ink-500">RMSE {performance.data.metrics.baseline_rmse.toFixed(3)}</p>
                </div>
              </div>
            </Card>
          ) : null}

          <p className="text-center text-[11px] text-ink-400">{t("forecast.disclaimer")}</p>
        </div>
      )}
    </div>
  );
}
