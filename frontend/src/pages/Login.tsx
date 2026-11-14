import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  ChefHat,
  KeyRound,
  Loader2,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  UserRound,
  UtensilsCrossed
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "../components/AppShell";
import { Button, TextField, useToast } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { homeForRole, useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

type Tab = "customer" | "staff" | "register";

interface HealthDb {
  status: string;
  counts: Record<string, number>;
}

export default function Login() {
  const { user, login, loginPin, register } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("customer");
  const [pinMode, setPinMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    username: "",
    password: "",
    pin: "",
    full_name: "",
    email: "",
    phone: "",
    address: ""
  });

  const health = useQuery({
    queryKey: ["health-db-public"],
    queryFn: () => api<HealthDb>("/health/db"),
    retry: 1,
    staleTime: 60_000
  });

  useEffect(() => {
    if (user) navigate(homeForRole(user.role), { replace: true });
  }, [user, navigate]);

  const update = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      let nextUser;
      if (tab === "register") {
        nextUser = await register({
          username: form.username.trim(),
          password: form.password,
          full_name: form.full_name.trim(),
          email: form.email.trim() || undefined,
          phone: form.phone.trim() || undefined,
          address: form.address.trim() || undefined
        });
        toast.success(t("login.create"));
      } else if (tab === "staff" && pinMode) {
        nextUser = await loginPin(form.username.trim(), form.pin.trim());
      } else {
        nextUser = await login(form.username.trim(), form.password);
      }
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== "/login" ? from : homeForRole(nextUser.role), { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-ink-900">
      <div className="absolute inset-0 opacity-90">
        <div className="absolute -end-40 -top-40 h-[520px] w-[520px] rounded-full bg-brand-500/25 blur-3xl" />
        <div className="absolute -bottom-52 -start-32 h-[520px] w-[520px] rounded-full bg-amber-300/10 blur-3xl" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.06),transparent_45%)]" />
      </div>

      <div className="relative mx-auto grid min-h-screen max-w-7xl lg:grid-cols-[1.05fr_0.95fr]">
        <div className="hidden flex-col justify-between p-12 lg:flex">
          <Logo light />
          <div className="max-w-xl">
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.16em] text-brand-200">
              <Sparkles className="h-3.5 w-3.5" /> AI-powered restaurant OS
            </p>
            <h1 className="font-display text-5xl font-extrabold leading-[1.08] tracking-tight text-white">
              One restaurant.
              <br />
              <span className="text-brand-400">One intelligent system.</span>
            </h1>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-white/60">
              Customer ordering, live kitchen operations, inventory, payments, analytics and demand forecasting — connected
              to your real MySQL menu.
            </p>
            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              {[
                { icon: <UtensilsCrossed className="h-4 w-4" />, label: "142 real menu items" },
                { icon: <ChefHat className="h-4 w-4" />, label: "Live kitchen board" },
                { icon: <Bot className="h-4 w-4" />, label: "Bilingual AI kiosk" },
                { icon: <ShieldCheck className="h-4 w-4" />, label: "Role-based access" }
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] px-3.5 py-3 text-sm text-white/75">
                  <span className="text-brand-300">{item.icon}</span>
                  {item.label}
                </div>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-6 text-xs text-white/35">
            <span>MySQL 8 · FastAPI · React</span>
            <span className={clsx("inline-flex items-center gap-1.5", health.data ? "text-emerald-400" : "text-white/35")}>
              <span className={clsx("h-1.5 w-1.5 rounded-full", health.data ? "bg-emerald-400" : "bg-white/30")} />
              {health.data ? `${health.data.counts?.menu_items ?? 0} dishes live` : "Connecting…"}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-center p-4 sm:p-8">
          <div className="w-full max-w-md">
            <div className="mb-6 flex justify-center lg:hidden">
              <Logo light />
            </div>
            <div className="rounded-3xl border border-white/10 bg-white p-6 shadow-2xl sm:p-8">
              <div className="mb-6">
                <h2 className="font-display text-2xl font-extrabold text-ink-900">{t("login.welcome")}</h2>
                <p className="mt-1 text-sm text-ink-500">{t("login.subtitle")}</p>
              </div>

              <div className="mb-6 grid grid-cols-2 rounded-xl bg-ink-100 p-1">
                <button
                  type="button"
                  onClick={() => {
                    setTab("customer");
                    setPinMode(false);
                    setError("");
                  }}
                  className={clsx(
                    "flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-bold transition",
                    tab === "customer" ? "bg-white text-ink-900 shadow-sm" : "text-ink-500 hover:text-ink-700"
                  )}
                >
                  <UserRound className="h-4 w-4" /> {t("login.customer")}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setTab("staff");
                    setError("");
                  }}
                  className={clsx(
                    "flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-bold transition",
                    tab !== "customer" ? "bg-white text-ink-900 shadow-sm" : "text-ink-500 hover:text-ink-700"
                  )}
                >
                  <ChefHat className="h-4 w-4" /> {t("login.staff")}
                </button>
              </div>

              <form onSubmit={submit} className="space-y-4">
                {tab === "register" ? (
                  <>
                    <TextField label={t("login.fullName")} value={form.full_name} onChange={update("full_name")} required minLength={2} placeholder="Nour Hassan" />
                    <div className="grid gap-4 sm:grid-cols-2">
                      <TextField label={t("login.username")} value={form.username} onChange={update("username")} required minLength={3} placeholder="nour" autoComplete="username" />
                      <TextField label={t("common.phone")} value={form.phone} onChange={update("phone")} placeholder="+20 100 000 0000" />
                    </div>
                    <TextField label={t("common.email")} value={form.email} onChange={update("email")} type="email" placeholder="you@example.com" />
                    <TextField label={t("common.address")} value={form.address} onChange={update("address")} placeholder="Street, city" />
                    <TextField label={t("login.password")} value={form.password} onChange={update("password")} type="password" required minLength={8} autoComplete="new-password" hint="At least 8 characters" />
                  </>
                ) : (
                  <>
                    <TextField label={t("login.username")} value={form.username} onChange={update("username")} required autoComplete="username" placeholder={tab === "staff" ? "chef" : "ahmed_ali"} />
                    {tab === "staff" && pinMode ? (
                      <TextField
                        label={t("login.pin")}
                        value={form.pin}
                        onChange={update("pin")}
                        type="password"
                        inputMode="numeric"
                        required
                        minLength={4}
                        maxLength={10}
                        autoComplete="one-time-code"
                        placeholder="••••"
                      />
                    ) : (
                      <TextField
                        label={t("login.password")}
                        value={form.password}
                        onChange={update("password")}
                        type="password"
                        required
                        minLength={4}
                        autoComplete="current-password"
                        placeholder="••••••••"
                      />
                    )}
                    {tab === "staff" ? (
                      <button
                        type="button"
                        onClick={() => {
                          setPinMode((prev) => !prev);
                          setError("");
                        }}
                        className="inline-flex items-center gap-1.5 text-xs font-bold text-brand-700 hover:underline"
                      >
                        {pinMode ? <LockKeyhole className="h-3.5 w-3.5" /> : <KeyRound className="h-3.5 w-3.5" />}
                        {pinMode ? t("login.passwordMode") : t("login.pinMode")}
                      </button>
                    ) : null}
                  </>
                )}

                {error ? (
                  <div className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-sm font-medium text-rose-800">
                    {error}
                  </div>
                ) : null}

                <Button type="submit" size="lg" className="w-full" loading={loading}>
                  {tab === "register" ? t("login.create") : t("login.signIn")}
                  {!loading ? <ArrowRight className="h-4 w-4" /> : null}
                </Button>
              </form>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-500">
                {tab === "register" ? (
                  <button className="font-semibold text-brand-700 hover:underline" onClick={() => setTab("customer")}>
                    {t("login.haveAccount")}
                  </button>
                ) : (
                  <button className="font-semibold text-brand-700 hover:underline" onClick={() => setTab("register")}>
                    {t("login.create")}
                  </button>
                )}
                <Link to="/kiosk" className="inline-flex items-center gap-1.5 font-semibold text-ink-600 hover:text-brand-700">
                  <Bot className="h-3.5 w-3.5" /> {t("login.kiosk")}
                </Link>
              </div>

              <div className="mt-5 flex items-start gap-2 rounded-xl bg-ink-50 px-3 py-2.5 text-[11px] leading-relaxed text-ink-500">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                {t("login.demoHint")}
              </div>
            </div>
            <p className="mt-4 text-center text-[11px] text-white/30">
              RestoMate AI · Seeded with the real Bremer menu
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
