import clsx from "clsx";
import {
  BarChart3,
  Bot,
  Boxes,
  CalendarClock,
  ClipboardList,
  ExternalLink,
  LayoutDashboard,
  LogOut,
  Menu as MenuIcon,
  PackageSearch,
  ScrollText,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Store,
  Truck,
  UserRound,
  UsersRound,
  UtensilsCrossed,
  X
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { homeForRole, useAuth } from "../lib/auth";
import { useCart } from "../lib/cart";
import { useI18n } from "../lib/i18n";
import type { Role } from "../lib/types";
import { initials } from "../lib/format";

interface NavItem {
  to: string;
  labelKey: string;
  icon: ReactNode;
  badge?: number;
}

export function Logo({ compact = false, light = false }: { compact?: boolean; light?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-500 text-white shadow-lg shadow-brand-900/20">
        <UtensilsCrossed className="h-5 w-5" />
      </span>
      {!compact ? (
        <div className="leading-tight">
          <p className={clsx("font-display text-base font-extrabold tracking-tight", light ? "text-white" : "text-ink-900")}>
            RestoMate <span className="text-brand-500">AI</span>
          </p>
          <p className={clsx("text-[10px] font-semibold uppercase tracking-[0.16em]", light ? "text-white/45" : "text-ink-400")}>
            Restaurant OS
          </p>
        </div>
      ) : null}
    </div>
  );
}

function navForRole(role: Role, t: (key: string) => string, cartCount: number): NavItem[] {
  if (role === "customer") {
    return [
      { to: "/menu", labelKey: "nav.menu", icon: <UtensilsCrossed className="h-4.5 w-4.5" />, badge: cartCount || undefined },
      { to: "/orders", labelKey: "nav.orders", icon: <ClipboardList className="h-4.5 w-4.5" /> },
      { to: "/profile", labelKey: "nav.profile", icon: <UserRound className="h-4.5 w-4.5" /> }
    ];
  }
  if (role === "chef" || role === "cashier") {
    return [
      { to: "/staff/board", labelKey: "nav.board", icon: <ShoppingBag className="h-4.5 w-4.5" /> },
      { to: "/profile", labelKey: "nav.profile", icon: <UserRound className="h-4.5 w-4.5" /> }
    ];
  }
  return [
    { to: "/manager/dashboard", labelKey: "nav.dashboard", icon: <LayoutDashboard className="h-4.5 w-4.5" /> },
    { to: "/staff/board", labelKey: "nav.board", icon: <ShoppingBag className="h-4.5 w-4.5" /> },
    { to: "/manager/inventory", labelKey: "nav.inventory", icon: <Boxes className="h-4.5 w-4.5" /> },
    { to: "/manager/suppliers", labelKey: "nav.suppliers", icon: <Truck className="h-4.5 w-4.5" /> },
    { to: "/manager/purchase-orders", labelKey: "nav.purchasing", icon: <PackageSearch className="h-4.5 w-4.5" /> },
    { to: "/manager/forecast", labelKey: "nav.forecast", icon: <BarChart3 className="h-4.5 w-4.5" /> },
    { to: "/manager/menu", labelKey: "nav.menuAdmin", icon: <Store className="h-4.5 w-4.5" /> },
    { to: "/manager/staff", labelKey: "nav.staff", icon: <UsersRound className="h-4.5 w-4.5" /> },
    { to: "/manager/audit", labelKey: "nav.audit", icon: <ScrollText className="h-4.5 w-4.5" /> }
  ];
}

export function AppShell({ children }: { children?: ReactNode }) {
  const { user, logout } = useAuth();
  const { t, lang, toggle, pick } = useI18n();
  const { count } = useCart();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  if (!user) return null;

  const nav = navForRole(user.role, t, count);
  const displayName = user.full_name || user.username;
  const roleLabel = t(`staff.${user.role}`);

  return (
    <div className="flex min-h-screen">
      {mobileOpen ? (
        <div className="fixed inset-0 z-40 bg-ink-900/50 backdrop-blur-sm lg:hidden" onClick={() => setMobileOpen(false)} />
      ) : null}

      <aside
        className={clsx(
          "fixed inset-y-0 start-0 z-50 flex w-[272px] flex-col bg-ink-900 text-white transition-transform duration-200 lg:static lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full rtl:translate-x-full lg:rtl:translate-x-0"
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-white/10 px-5">
          <Logo light />
          <button className="rounded-lg p-1.5 text-white/60 hover:bg-white/10 lg:hidden" onClick={() => setMobileOpen(false)}>
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-3 pb-2 pt-4">
          <p className="px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-white/35">
            {user.role === "customer" ? "My restaurant" : "Operations"}
          </p>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-4">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/menu"}
              className={({ isActive }) =>
                clsx(
                  "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition",
                  isActive ? "bg-brand-500 text-white shadow-lg shadow-brand-900/25" : "text-white/65 hover:bg-white/10 hover:text-white"
                )
              }
            >
              {item.icon}
              <span className="flex-1">{t(item.labelKey)}</span>
              {item.badge ? (
                <span className="grid h-5 min-w-5 place-items-center rounded-full bg-white px-1 text-[10px] font-extrabold text-brand-700">
                  {item.badge}
                </span>
              ) : null}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/10 p-3">
          <a
            href="/kiosk"
            target="_blank"
            rel="noreferrer"
            className="mb-2 flex items-center gap-3 rounded-xl bg-white/5 px-3 py-2.5 text-sm font-semibold text-white/70 transition hover:bg-white/10 hover:text-white"
          >
            <Bot className="h-4.5 w-4.5" />
            <span className="flex-1">{t("nav.kiosk")}</span>
            <ExternalLink className="h-3.5 w-3.5 opacity-60" />
          </a>
          <div className="flex items-center gap-3 rounded-xl px-2 py-2">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-500/20 text-sm font-bold text-brand-200">
              {initials(displayName)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-white">{displayName}</p>
              <p className="truncate text-[11px] text-white/45">{roleLabel}</p>
            </div>
            <button
              onClick={() => void logout()}
              title={t("nav.logout")}
              className="rounded-lg p-2 text-white/50 transition hover:bg-white/10 hover:text-white"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-ink-100 bg-white/85 px-4 backdrop-blur-lg sm:px-6 lg:px-8">
          <button
            className="rounded-xl border border-ink-200 p-2 text-ink-600 lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <MenuIcon className="h-5 w-5" />
          </button>
          <div className="hidden items-center gap-2 text-sm text-ink-500 sm:flex">
            <CalendarClock className="h-4 w-4 text-ink-400" />
            <span>
              {new Date().toLocaleDateString(lang === "ar" ? "ar-EG" : "en-GB", {
                weekday: "long",
                day: "2-digit",
                month: "long"
              })}
            </span>
          </div>
          <div className="flex-1" />
          {user.role === "customer" ? (
            <NavLink
              to="/menu#cart"
              className="relative hidden items-center gap-2 rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm font-semibold text-ink-700 hover:bg-ink-50 sm:flex"
            >
              <ShoppingCart className="h-4 w-4" />
              {t("menu.cart")}
              {count ? (
                <span className="grid h-5 min-w-5 place-items-center rounded-full bg-brand-500 px-1 text-[10px] font-extrabold text-white">
                  {count}
                </span>
              ) : null}
            </NavLink>
          ) : null}
          <button
            onClick={toggle}
            className="rounded-xl border border-ink-200 bg-white px-3 py-2 text-xs font-bold text-ink-600 transition hover:bg-ink-50"
          >
            {t("common.language")}
          </button>
          <div className="hidden items-center gap-2 rounded-xl border border-ink-100 bg-ink-50 px-3 py-1.5 sm:flex">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-ink-900 text-[10px] font-bold text-white">
              {initials(displayName)}
            </span>
            <div className="leading-tight">
              <p className="text-xs font-bold text-ink-800">{displayName}</p>
              <p className="text-[10px] text-ink-500">{roleLabel}</p>
            </div>
          </div>
          <NavLink
            to={homeForRole(user.role)}
            className="hidden rounded-xl bg-ink-900 p-2 text-white hover:bg-ink-800 sm:block"
            title={pick("Home", "الرئيسية")}
          >
            <Sparkles className="h-4 w-4" />
          </NavLink>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children ?? <Outlet />}
        </main>
      </div>
    </div>
  );
}
