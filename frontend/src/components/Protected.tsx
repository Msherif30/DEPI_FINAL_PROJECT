import { Navigate, Outlet, useLocation } from "react-router-dom";
import { homeForRole, useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import type { Role } from "../lib/types";
import { Loading } from "./ui";

export function RequireAuth({ children }: { children?: React.ReactNode }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Loading />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children ?? <Outlet />}</>;
}

export function RequireRole({ roles, children }: { roles: Role[]; children?: React.ReactNode }) {
  const { user } = useAuth();
  const { t } = useI18n();
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) {
    return (
      <div className="mx-auto max-w-lg py-20 text-center">
        <p className="text-sm font-semibold text-rose-600">{t("error.forbidden")}</p>
        <a href={homeForRole(user.role)} className="link mt-3 inline-block">
          {t("common.back")}
        </a>
      </div>
    );
  }
  return <>{children ?? <Outlet />}</>;
}

export function HomeRedirect() {
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Loading />
      </div>
    );
  }
  return <Navigate to={user ? homeForRole(user.role) : "/login"} replace />;
}
