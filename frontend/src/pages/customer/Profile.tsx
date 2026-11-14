import { useMutation, useQuery } from "@tanstack/react-query";
import { BadgeCheck, KeyRound, Mail, MapPin, Phone, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Button, Card, Loading, PageHeader, TextField, useToast } from "../../components/ui";
import { api, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { dateTime } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { CustomerProfile, User } from "../../lib/types";

interface MeResponse {
  user: User;
  customer: CustomerProfile | null;
}

export default function Profile() {
  const { t } = useI18n();
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState({ full_name: "", email: "", phone: "", address: "" });
  const [passwords, setPasswords] = useState({ current_password: "", new_password: "" });

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<MeResponse>("/auth/me")
  });

  useEffect(() => {
    if (!me.data) return;
    setForm({
      full_name: me.data.user.full_name ?? "",
      email: me.data.user.email ?? "",
      phone: me.data.customer?.phone ?? "",
      address: me.data.customer?.address ?? ""
    });
  }, [me.data]);

  const save = useMutation({
    mutationFn: () =>
      api<MeResponse>("/auth/me", {
        method: "PATCH",
        body: {
          full_name: form.full_name || undefined,
          email: form.email || undefined,
          phone: form.phone || undefined,
          address: form.address || undefined
        }
      }),
    onSuccess: (data) => {
      setUser(data.user);
      toast.success(t("profile.saved"));
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const changePassword = useMutation({
    mutationFn: () =>
      api("/auth/me/password", {
        method: "POST",
        body: passwords
      }),
    onSuccess: () => {
      setPasswords({ current_password: "", new_password: "" });
      toast.success(t("profile.passwordChanged"));
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  if (me.isLoading) return <Loading />;
  if (me.isError) return <div className="text-sm text-rose-700">{errorMessage(me.error)}</div>;

  const profile = me.data?.customer;
  const account = me.data?.user ?? user;

  return (
    <div>
      <PageHeader eyebrow={t("app.name")} title={t("profile.title")} subtitle={t("profile.subtitle")} />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <Card className="card-pad">
            <h2 className="mb-4 inline-flex items-center gap-2 font-display text-base font-bold text-ink-900">
              <UserRound className="h-4.5 w-4.5 text-brand-600" /> {t("profile.title")}
            </h2>
            <form
              className="grid gap-4 sm:grid-cols-2"
              onSubmit={(event) => {
                event.preventDefault();
                save.mutate();
              }}
            >
              <TextField label={t("common.name")} value={form.full_name} onChange={(event) => setForm((prev) => ({ ...prev, full_name: event.target.value }))} required />
              <TextField label={t("common.email")} type="email" value={form.email} onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))} />
              <TextField label={t("common.phone")} value={form.phone} onChange={(event) => setForm((prev) => ({ ...prev, phone: event.target.value }))} />
              <TextField label={t("common.address")} value={form.address} onChange={(event) => setForm((prev) => ({ ...prev, address: event.target.value }))} />
              <div className="sm:col-span-2 flex justify-end">
                <Button type="submit" loading={save.isPending}>
                  {t("common.save")}
                </Button>
              </div>
            </form>
          </Card>

          <Card className="card-pad">
            <h2 className="mb-4 inline-flex items-center gap-2 font-display text-base font-bold text-ink-900">
              <ShieldCheck className="h-4.5 w-4.5 text-brand-600" /> {t("profile.security")}
            </h2>
            <form
              className="grid gap-4 sm:grid-cols-2"
              onSubmit={(event) => {
                event.preventDefault();
                changePassword.mutate();
              }}
            >
              <TextField
                label={t("profile.currentPassword")}
                type="password"
                value={passwords.current_password}
                onChange={(event) => setPasswords((prev) => ({ ...prev, current_password: event.target.value }))}
                required
                autoComplete="current-password"
              />
              <TextField
                label={t("profile.newPassword")}
                type="password"
                value={passwords.new_password}
                onChange={(event) => setPasswords((prev) => ({ ...prev, new_password: event.target.value }))}
                required
                minLength={8}
                autoComplete="new-password"
                hint="At least 8 characters"
              />
              <div className="sm:col-span-2 flex justify-end">
                <Button type="submit" variant="secondary" loading={changePassword.isPending}>
                  <KeyRound className="h-4 w-4" /> {t("profile.changePassword")}
                </Button>
              </div>
            </form>
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="card-pad">
            <div className="mb-4 flex items-center gap-3">
              <span className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-100 font-display text-lg font-extrabold text-brand-700">
                {(account?.full_name ?? account?.username ?? "?").slice(0, 1).toUpperCase()}
              </span>
              <div>
                <p className="font-display text-base font-bold text-ink-900">{account?.full_name ?? account?.username}</p>
                <p className="text-xs text-ink-500">@{account?.username}</p>
              </div>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-ink-500">{t("common.role")}</span>
                <Badge tone="brand">{t(`staff.${account?.role ?? "customer"}`)}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-500">{t("common.status")}</span>
                {account?.is_active ? <Badge tone="success"><BadgeCheck className="h-3 w-3" /> {t("common.active")}</Badge> : <Badge tone="danger">{t("common.inactive")}</Badge>}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-500">{t("common.since")}</span>
                <span className="text-ink-700">{dateTime(account?.created_at)}</span>
              </div>
            </div>
          </Card>

          {profile ? (
            <Card className="card-pad">
              <h3 className="mb-3 font-display text-sm font-bold text-ink-900">{t("profile.title")}</h3>
              <div className="space-y-2.5 text-sm text-ink-600">
                <p className="inline-flex items-center gap-2"><Phone className="h-4 w-4 text-ink-400" /> {profile.phone || "—"}</p>
                <p className="inline-flex items-center gap-2"><Mail className="h-4 w-4 text-ink-400" /> {account?.email || "—"}</p>
                <p className="inline-flex items-start gap-2"><MapPin className="mt-0.5 h-4 w-4 text-ink-400" /> {profile.address || "—"}</p>
              </div>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
