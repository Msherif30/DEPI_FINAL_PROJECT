import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChefHat,
  KeyRound,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  UserRound,
  UsersRound
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Loading,
  Modal,
  PageHeader,
  SelectField,
  TextField,
  useToast
} from "../../components/ui";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dateTime, initials } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { Role, User } from "../../lib/types";

const STAFF_ROLES: Role[] = ["chef", "cashier", "manager"];

const emptyCreate = {
  username: "",
  full_name: "",
  email: "",
  password: "",
  pin: "",
  role: "chef" as Role
};

const emptyEdit = {
  full_name: "",
  email: "",
  role: "chef" as Role,
  is_active: true,
  pin: ""
};

export default function Staff() {
  const { t, pick } = useI18n();
  const { user: current } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<"all" | Role>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(emptyCreate);
  const [editing, setEditing] = useState<User | null>(null);
  const [editForm, setEditForm] = useState(emptyEdit);
  const [passwordFor, setPasswordFor] = useState<User | null>(null);
  const [newPassword, setNewPassword] = useState("");

  const users = useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/users") });

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (users.data ?? []).filter((row) => {
      if (roleFilter !== "all" && row.role !== roleFilter) return false;
      if (!term) return true;
      return [row.username, row.full_name, row.email].some((value) => (value ?? "").toLowerCase().includes(term));
    });
  }, [users.data, roleFilter, search]);

  const counts = useMemo(() => {
    const rows = users.data ?? [];
    return {
      total: rows.length,
      staff: rows.filter((row) => row.role !== "customer").length,
      active: rows.filter((row) => row.is_active).length
    };
  }, [users.data]);

  const createMutation = useMutation({
    mutationFn: () =>
      api<User>("/users", {
        method: "POST",
        body: {
          username: createForm.username.trim(),
          full_name: createForm.full_name.trim(),
          email: createForm.email.trim() || undefined,
          password: createForm.password,
          pin: createForm.pin.trim() || undefined,
          role: createForm.role
        }
      }),
    onSuccess: () => {
      toast.success(t("staff.created"));
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setCreateOpen(false);
      setCreateForm(emptyCreate);
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api<User>(`/users/${editing?.user_id}`, {
        method: "PATCH",
        body: {
          full_name: editForm.full_name.trim(),
          email: editForm.email.trim() || undefined,
          role: editForm.role,
          is_active: editForm.is_active,
          pin: editForm.pin.trim() || undefined
        }
      }),
    onSuccess: () => {
      toast.success(t("staff.updated"));
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setEditing(null);
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const resetMutation = useMutation({
    mutationFn: () =>
      api(`/users/${passwordFor?.user_id}/reset-password`, {
        method: "POST",
        body: { new_password: newPassword }
      }),
    onSuccess: () => {
      toast.success(pick("Password reset", "تم إعادة تعيين كلمة المرور"));
      setPasswordFor(null);
      setNewPassword("");
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const openEdit = (row: User) => {
    setEditing(row);
    setEditForm({
      full_name: row.full_name ?? "",
      email: row.email ?? "",
      role: row.role,
      is_active: row.is_active,
      pin: ""
    });
  };

  const roleIcon = (role: Role) => {
    if (role === "chef") return <ChefHat className="h-4 w-4" />;
    if (role === "manager") return <ShieldCheck className="h-4 w-4" />;
    return <UserRound className="h-4 w-4" />;
  };

  const roleTone = (role: Role): "violet" | "brand" | "info" | "neutral" =>
    role === "manager" ? "violet" : role === "chef" ? "brand" : role === "cashier" ? "info" : "neutral";

  const roleFilters: ("all" | Role)[] = ["all", "chef", "cashier", "manager", "customer"];

  return (
    <div>
      <PageHeader
        eyebrow={pick("Manager", "الإدارة")}
        title={t("staff.title")}
        subtitle={t("staff.subtitle")}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => void users.refetch()} loading={users.isFetching}>
              <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
            </Button>
            <Button onClick={() => { setCreateForm(emptyCreate); setCreateOpen(true); }}>
              <Plus className="h-4 w-4" /> {t("staff.add")}
            </Button>
          </div>
        }
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        {[
          { label: pick("All accounts", "كل الحسابات"), value: counts.total, icon: <UsersRound className="h-4 w-4" /> },
          { label: pick("Staff members", "أعضاء الفريق"), value: counts.staff, icon: <ChefHat className="h-4 w-4" /> },
          { label: pick("Active accounts", "حسابات نشطة"), value: counts.active, icon: <ShieldCheck className="h-4 w-4" /> }
        ].map((stat) => (
          <Card key={stat.label} className="flex items-center gap-3 px-5 py-4">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-700">{stat.icon}</span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">{stat.label}</p>
              <p className="font-display text-xl font-extrabold text-ink-900">{stat.value}</p>
            </div>
          </Card>
        ))}
      </div>

      <Card className="mb-4 flex flex-col gap-3 p-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <input
            className="field ps-9"
            placeholder={t("common.search")}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {roleFilters.map((role) => (
            <button
              key={role}
              onClick={() => setRoleFilter(role)}
              className={
                roleFilter === role
                  ? "rounded-lg bg-ink-900 px-3 py-1.5 text-xs font-bold capitalize text-white"
                  : "rounded-lg bg-ink-100 px-3 py-1.5 text-xs font-bold capitalize text-ink-600 hover:bg-ink-200"
              }
            >
              {role === "all" ? t("common.all") : t(`staff.${role}`)}
            </button>
          ))}
        </div>
      </Card>

      {users.isLoading ? (
        <Loading />
      ) : !filtered.length ? (
        <EmptyState title={pick("No accounts match this filter.", "لا توجد حسابات مطابقة.")} icon={<UsersRound className="h-6 w-6" />} />
      ) : (
        <Card className="overflow-hidden">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("common.name")}</th>
                  <th>{t("common.role")}</th>
                  <th>{t("common.status")}</th>
                  <th>{pick("PIN", "الرقم السري")}</th>
                  <th>{pick("Last login", "آخر دخول")}</th>
                  <th className="text-end">{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.user_id}>
                    <td>
                      <div className="flex items-center gap-3">
                        <span className="grid h-9 w-9 place-items-center rounded-full bg-ink-900 text-[11px] font-bold text-white">
                          {initials(row.full_name || row.username)}
                        </span>
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-ink-900">
                            {row.full_name || row.username}
                            {row.user_id === current?.user_id ? (
                              <span className="ms-2 text-[10px] font-bold uppercase text-brand-600">{pick("You", "أنت")}</span>
                            ) : null}
                          </p>
                          <p className="truncate text-xs text-ink-400">
                            @{row.username}
                            {row.email ? ` · ${row.email}` : ""}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td>
                      <Badge tone={roleTone(row.role)}>
                        {roleIcon(row.role)} {t(`staff.${row.role}`)}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone={row.is_active ? "success" : "neutral"}>
                        {row.is_active ? t("common.active") : t("common.inactive")}
                      </Badge>
                    </td>
                    <td className="text-xs text-ink-500">{row.has_pin ? pick("Configured", "مُعرّف") : pick("Not set", "غير مُعرّف")}</td>
                    <td className="text-xs text-ink-500">{row.last_login_at ? dateTime(row.last_login_at) : "—"}</td>
                    <td>
                      <div className="flex justify-end gap-1.5">
                        <Button size="sm" variant="secondary" onClick={() => openEdit(row)}>
                          <Pencil className="h-3.5 w-3.5" /> {t("common.edit")}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => { setPasswordFor(row); setNewPassword(""); }}>
                          <KeyRound className="h-3.5 w-3.5" /> {t("staff.resetPassword")}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title={t("staff.add")}
        description={pick("The password is hashed with bcrypt and never shown again.", "كلمة المرور تُهشّر بـ bcrypt ولا تُعرض مرة أخرى.")}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>{t("common.cancel")}</Button>
            <Button loading={createMutation.isPending} onClick={() => createMutation.mutate()}>{t("common.save")}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label={t("staff.username")}
            value={createForm.username}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, username: event.target.value }))}
            placeholder="chef.ali"
            pattern="[A-Za-z0-9_.-]+"
            minLength={3}
            required
          />
          <TextField
            label={pick("Full name", "الاسم بالكامل")}
            value={createForm.full_name}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, full_name: event.target.value }))}
            minLength={2}
            required
          />
          <TextField
            label={t("common.email")}
            type="email"
            value={createForm.email}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, email: event.target.value }))}
          />
          <SelectField
            label={t("common.role")}
            value={createForm.role}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, role: event.target.value as Role }))}
          >
            {STAFF_ROLES.map((role) => (
              <option key={role} value={role}>{t(`staff.${role}`)}</option>
            ))}
          </SelectField>
          <TextField
            label={t("login.password")}
            type="password"
            value={createForm.password}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, password: event.target.value }))}
            minLength={8}
            hint={pick("At least 8 characters", "٨ أحرف على الأقل")}
            required
          />
          <TextField
            label={t("staff.pin")}
            value={createForm.pin}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, pin: event.target.value }))}
            minLength={4}
            maxLength={10}
            inputMode="numeric"
            hint={pick("4–10 digits, hashed at rest", "٤–١٠ أرقام، تُهشّر عند التخزين")}
          />
        </div>
      </Modal>

      <Modal
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        title={pick("Edit staff account", "تعديل حساب عضو الفريق")}
        description={editing ? `@${editing.username}` : undefined}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(null)}>{t("common.cancel")}</Button>
            <Button loading={updateMutation.isPending} onClick={() => updateMutation.mutate()}>{t("common.save")}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label={pick("Full name", "الاسم بالكامل")}
            value={editForm.full_name}
            onChange={(event) => setEditForm((prev) => ({ ...prev, full_name: event.target.value }))}
            minLength={2}
          />
          <TextField
            label={t("common.email")}
            type="email"
            value={editForm.email}
            onChange={(event) => setEditForm((prev) => ({ ...prev, email: event.target.value }))}
          />
          <SelectField
            label={t("common.role")}
            value={editForm.role}
            onChange={(event) => setEditForm((prev) => ({ ...prev, role: event.target.value as Role }))}
          >
            {STAFF_ROLES.map((role) => (
              <option key={role} value={role}>{t(`staff.${role}`)}</option>
            ))}
          </SelectField>
          <TextField
            label={t("staff.pin")}
            value={editForm.pin}
            onChange={(event) => setEditForm((prev) => ({ ...prev, pin: event.target.value }))}
            minLength={4}
            maxLength={10}
            inputMode="numeric"
            hint={pick("Leave blank to keep the current PIN", "اتركه فاضياً للإبقاء على الرقم الحالي")}
          />
          <label className="flex items-center gap-2 text-sm font-semibold text-ink-700">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-ink-300 text-brand-600"
              checked={editForm.is_active}
              disabled={editing?.user_id === current?.user_id}
              onChange={(event) => setEditForm((prev) => ({ ...prev, is_active: event.target.checked }))}
            />
            {t("common.active")}
          </label>
        </div>
      </Modal>

      <Modal
        open={Boolean(passwordFor)}
        onClose={() => { setPasswordFor(null); setNewPassword(""); }}
        title={t("staff.resetPassword")}
        description={passwordFor ? `@${passwordFor.username}` : undefined}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => { setPasswordFor(null); setNewPassword(""); }}>{t("common.cancel")}</Button>
            <Button loading={resetMutation.isPending} disabled={newPassword.length < 8} onClick={() => resetMutation.mutate()}>
              {t("staff.resetPassword")}
            </Button>
          </>
        }
      >
        <TextField
          label={t("staff.newPassword")}
          type="password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
          minLength={8}
          hint={pick("The user must change it at next sign-in.", "يجب على المستخدم تغييرها عند الدخول التالي.")}
        />
      </Modal>
    </div>
  );
}
