import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { HomeRedirect, RequireAuth, RequireRole } from "./components/Protected";
import Kiosk from "./pages/Kiosk";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Menu from "./pages/customer/Menu";
import OrderDetail from "./pages/customer/OrderDetail";
import Orders from "./pages/customer/Orders";
import Profile from "./pages/customer/Profile";
import Audit from "./pages/manager/Audit";
import Dashboard from "./pages/manager/Dashboard";
import Forecast from "./pages/manager/Forecast";
import Inventory from "./pages/manager/Inventory";
import MenuAdmin from "./pages/manager/MenuAdmin";
import PurchaseOrders from "./pages/manager/PurchaseOrders";
import Staff from "./pages/manager/Staff";
import Suppliers from "./pages/manager/Suppliers";
import StaffBoard from "./pages/staff/StaffBoard";

const STAFF_ROLES = ["chef", "cashier", "manager"] as const;
const MANAGER_ROLES = ["manager"] as const;

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<Login />} />
      <Route path="/kiosk" element={<Kiosk />} />

      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/menu" element={<Menu />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/orders/:orderId" element={<OrderDetail />} />
          <Route path="/profile" element={<Profile />} />

          <Route
            path="/staff/board"
            element={
              <RequireRole roles={[...STAFF_ROLES]}>
                <StaffBoard />
              </RequireRole>
            }
          />

          <Route
            path="/manager/dashboard"
            element={
              <RequireRole roles={[...MANAGER_ROLES]}>
                <Dashboard />
              </RequireRole>
            }
          />
          <Route
            path="/manager/inventory"
            element={
              <RequireRole roles={[...MANAGER_ROLES]}>
                <Inventory />
              </RequireRole>
            }
          />
          <Route
            path="/manager/suppliers"
            element={
              <RequireRole roles={[...MANAGER_ROLES]}>
                <Suppliers />
              </RequireRole>
            }
          />
          <Route
            path="/manager/purchase-orders"
            element={
              <RequireRole roles={[...MANAGER_ROLES]}>
                <PurchaseOrders />
              </RequireRole>
            }
          />
          <Route
            path="/manager/forecast"
            element={
              <RequireRole roles={[...MANAGER_ROLES]}>
                <Forecast />
              </RequireRole>
            }
          />
          <Route
            path="/manager/menu"
            element={
              <RequireRole roles={[...MANAGER_ROLES]}>
                <MenuAdmin />
              </RequireRole>
            }
          />
          <Route
            path="/manager/staff"
            element={
              <RequireRole roles={[...MANAGER_ROLES]}>
                <Staff />
              </RequireRole>
            }
          />
          <Route
            path="/manager/audit"
            element={
              <RequireRole roles={[...MANAGER_ROLES]}>
                <Audit />
              </RequireRole>
            }
          />
        </Route>
      </Route>

      <Route path="/dashboard" element={<Navigate to="/manager/dashboard" replace />} />
      <Route path="/manager" element={<Navigate to="/manager/dashboard" replace />} />
      <Route path="/board" element={<Navigate to="/staff/board" replace />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
