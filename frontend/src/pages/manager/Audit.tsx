import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  Filter,
  Globe2,
  RefreshCw,
  ScrollText,
  Search,
  ShieldCheck,
  UserRound
} from "lucide-react";
import { Fragment, useMemo, useState } from "react";
import { Badge, Button, Card, EmptyState, Loading, PageHeader } from "../../components/ui";
import { api, qs } from "../../lib/api";
import { dateTime } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { AuditLogEntry } from "../../lib/types";

function actionTone(action: string): "success" | "warn" | "danger" | "info" | "brand" | "neutral" {
  if (/(delete|retire|cancel|deactivate|failed)/.test(action)) return "danger";
  if (/(refund|adjust|waste)/.test(action)) return "warn";
  if (/(payment|paid|confirm|complete)/.test(action)) return "success";
  if (/(login|logout|session)/.test(action)) return "info";
  if (/(create|update|receive|train)/.test(action)) return "brand";
  return "neutral";
}

export default function Audit() {
  const { t, pick } = useI18n();
  const [limit, setLimit] = useState(100);
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState("all");
  const [expanded, setExpanded] = useState<number | null>(null);

  const logs = useQuery({
    queryKey: ["audit-logs", limit],
    queryFn: () => api<AuditLogEntry[]>(`/analytics/audit-logs${qs({ limit })}`)
  });

  const actions = useMemo(() => {
    const set = new Set((logs.data ?? []).map((row) => row.action));
    return ["all", ...Array.from(set).sort()];
  }, [logs.data]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (logs.data ?? []).filter((row) => {
      if (actionFilter !== "all" && row.action !== actionFilter) return false;
      if (!term) return true;
      return [row.action, row.entity_type, row.entity_id, row.user_name, row.ip_address].some((value) =>
        (value ?? "").toLowerCase().includes(term)
      );
    });
  }, [actionFilter, logs.data, search]);

  return (
    <div>
      <PageHeader
        eyebrow={pick("Manager", "الإدارة")}
        title={t("audit.title")}
        subtitle={t("audit.subtitle")}
        actions={
          <Button variant="secondary" onClick={() => void logs.refetch()} loading={logs.isFetching}>
            <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        {[
          { label: pick("Events shown", "الأحداث المعروضة"), value: filtered.length, icon: <ScrollText className="h-4 w-4" /> },
          { label: pick("Distinct actions", "إجراءات مختلفة"), value: Math.max(0, actions.length - 1), icon: <Filter className="h-4 w-4" /> },
          { label: pick("Source", "المصدر"), value: pick("Live database", "قاعدة البيانات"), icon: <ShieldCheck className="h-4 w-4" /> }
        ].map((stat) => (
          <Card key={stat.label} className="flex items-center gap-3 px-5 py-4">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-700">{stat.icon}</span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">{stat.label}</p>
              <p className="font-display text-lg font-extrabold text-ink-900">{stat.value}</p>
            </div>
          </Card>
        ))}
      </div>

      <Card className="mb-4 flex flex-col gap-3 p-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <input
            className="field ps-9"
            placeholder={pick("Search action, entity, actor or IP…", "ابحث بالإجراء أو الكيان أو المستخدم أو IP…")}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <select className="field sm:w-56" value={actionFilter} onChange={(event) => setActionFilter(event.target.value)}>
          {actions.map((action) => (
            <option key={action} value={action}>
              {action === "all" ? pick("All actions", "كل الإجراءات") : action}
            </option>
          ))}
        </select>
        <select className="field sm:w-36" value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
          {[50, 100, 200].map((value) => (
            <option key={value} value={value}>{value} {pick("rows", "سجل")}</option>
          ))}
        </select>
      </Card>

      {logs.isLoading ? (
        <Loading />
      ) : !filtered.length ? (
        <EmptyState
          title={pick("No audit events match this filter.", "لا توجد أحداث تدقيق مطابقة.")}
          description={pick("Operational and security events appear here automatically.", "تظهر أحداث التشغيل والأمان هنا تلقائياً.")}
          icon={<ScrollText className="h-6 w-6" />}
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="w-8" />
                  <th>{t("audit.when")}</th>
                  <th>{t("audit.action")}</th>
                  <th>{t("audit.entity")}</th>
                  <th>{t("audit.actor")}</th>
                  <th>{pick("IP", "IP")}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => {
                  const isOpen = expanded === row.audit_id;
                  return (
                    <Fragment key={row.audit_id}>
                      <tr
                        className="cursor-pointer"
                        onClick={() => setExpanded(isOpen ? null : row.audit_id)}
                      >
                        <td className="text-ink-400">
                          {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4 rtl:rotate-180" />}
                        </td>
                        <td className="whitespace-nowrap text-xs text-ink-500">{dateTime(row.created_at)}</td>
                        <td>
                          <Badge tone={actionTone(row.action)}>{row.action}</Badge>
                        </td>
                        <td className="text-xs text-ink-600">
                          <span className="font-semibold">{row.entity_type}</span>
                          {row.entity_id ? <span className="text-ink-400"> #{row.entity_id}</span> : null}
                        </td>
                        <td className="text-xs text-ink-600">
                          {row.user_name ? (
                            <span className="inline-flex items-center gap-1.5">
                              <UserRound className="h-3.5 w-3.5 text-ink-400" /> {row.user_name}
                            </span>
                          ) : (
                            <span className="text-ink-400">{pick("System / public", "النظام / عام")}</span>
                          )}
                        </td>
                        <td className="text-xs text-ink-500">
                          {row.ip_address ? (
                            <span className="inline-flex items-center gap-1.5">
                              <Globe2 className="h-3.5 w-3.5 text-ink-400" /> {row.ip_address}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                      {isOpen ? (
                        <tr className="bg-ink-50/70">
                          <td />
                          <td colSpan={5} className="py-3">
                            <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-ink-400">
                              {pick("Event details", "تفاصيل الحدث")} #{row.audit_id}
                            </p>
                            <pre className="scroll-thin max-h-48 overflow-auto rounded-xl bg-ink-900 p-3 text-xs text-emerald-100">
                              {JSON.stringify(row.details ?? {}, null, 2)}
                            </pre>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <p className="mt-3 text-xs text-ink-400">
        {pick(
          "Audit entries are written by the backend on authentication, ordering, inventory, menu and staff changes.",
          "تُكتب سجلات التدقيق من الخادم عند المصادقة والطلبات والمخزون والمنيو وتغييرات الفريق."
        )}
      </p>
    </div>
  );
}
