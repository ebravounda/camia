import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  LayoutDashboard, Cctv, Cpu, AlertTriangle, CreditCard, Settings,
  Shield, LogOut, Cog,
} from "lucide-react";

const nav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/cameras", label: "Cámaras", icon: Cctv, testid: "nav-cameras" },
  { to: "/devices", label: "Raspberry Pi", icon: Cpu, testid: "nav-devices" },
  { to: "/events", label: "Eventos", icon: AlertTriangle, testid: "nav-events" },
  { to: "/pricing", label: "Planes", icon: CreditCard, testid: "nav-pricing" },
  { to: "/settings", label: "Configuración", icon: Settings, testid: "nav-settings" },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <aside
      data-testid="app-sidebar"
      className="hidden md:flex flex-col w-64 shrink-0 border-r border-white/10 bg-[#0E1017] min-h-screen sticky top-0"
    >
      <div className="px-6 py-6 border-b border-white/10">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-[0_0_14px_rgba(59,130,246,0.45)]">
            <Cctv className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-display text-base font-bold tracking-tight">SmartCam</div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500 font-mono">SaaS</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-5 space-y-1">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            data-testid={item.testid}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors group ${
                isActive
                  ? "bg-blue-500/10 text-blue-400 border-l-2 border-blue-500"
                  : "text-gray-400 hover:text-white hover:bg-white/5 border-l-2 border-transparent"
              }`
            }
          >
            <item.icon className="w-4 h-4" />
            <span className="font-medium">{item.label}</span>
          </NavLink>
        ))}

        {user?.role === "super_admin" && (
          <>
            <div className="pt-5 pb-2 px-3 text-[10px] uppercase tracking-[0.2em] text-gray-600 font-mono">
              Plataforma
            </div>
            <NavLink
              to="/admin"
              data-testid="nav-admin"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-blue-500/10 text-blue-400 border-l-2 border-blue-500"
                    : "text-gray-400 hover:text-white hover:bg-white/5 border-l-2 border-transparent"
                }`
              }
            >
              <Shield className="w-4 h-4" />
              <span className="font-medium">Super Admin</span>
            </NavLink>
          </>
        )}
      </nav>

      <div className="px-3 py-4 border-t border-white/10">
        <div className="flex items-center gap-3 px-2 py-2 rounded-lg">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-xs font-bold uppercase">
            {user?.name?.[0] || "U"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate" data-testid="sidebar-user-name">{user?.name}</div>
            <div className="text-[11px] text-gray-500 truncate font-mono">{user?.email}</div>
          </div>
          <button
            data-testid="sidebar-logout-button"
            onClick={onLogout}
            className="p-2 rounded-md text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
            title="Cerrar sesión"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
