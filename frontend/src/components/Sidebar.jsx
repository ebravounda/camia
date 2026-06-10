import { NavLink, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import {
  LayoutDashboard, Cctv, Cpu, AlertTriangle, CreditCard, Settings,
  Shield, LogOut, ScanFace,
} from "lucide-react";

const nav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/cameras", label: "Cámaras", icon: Cctv, testid: "nav-cameras" },
  { to: "/devices", label: "Raspberry Pi", icon: Cpu, testid: "nav-devices" },
  { to: "/events", label: "Eventos", icon: AlertTriangle, testid: "nav-events" },
  { to: "/faces", label: "Caras", icon: ScanFace, testid: "nav-faces" },
  { to: "/pricing", label: "Planes", icon: CreditCard, testid: "nav-pricing" },
  { to: "/settings", label: "Configuración", icon: Settings, testid: "nav-settings" },
];

const item = (i) => ({
  hidden: { opacity: 0, x: -8 },
  show: { opacity: 1, x: 0, transition: { delay: 0.03 * i, duration: 0.22, ease: [0.22, 1, 0.36, 1] } },
});

export default function Sidebar({ onNavigate }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  const NavRow = ({ to, label, Icon, testid, idx }) => (
    <motion.div variants={item(idx)} initial="hidden" animate="show">
      <NavLink
        to={to}
        onClick={onNavigate}
        data-testid={testid}
        className={({ isActive }) =>
          `relative flex items-center gap-3 px-3 py-2.5 text-sm transition-all duration-200 group ${
            isActive
              ? "bg-[#C8FF00] text-black font-semibold"
              : "text-gray-400 hover:text-white hover:bg-white/[0.04]"
          }`
        }
      >
        {({ isActive }) => (
          <>
            {!isActive && (
              <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0 h-5 bg-[#C8FF00] group-hover:w-0.5 transition-all duration-200" />
            )}
            <Icon className="w-4 h-4 shrink-0 group-hover:scale-110 transition-transform duration-200" strokeWidth={2} />
            <span className="font-medium">{label}</span>
          </>
        )}
      </NavLink>
    </motion.div>
  );

  return (
    <aside
      data-testid="app-sidebar"
      className="flex flex-col w-64 shrink-0 border-r border-white/10 bg-[#0A0A0A] min-h-screen"
    >
      <div className="px-6 py-7 border-b border-white/10">
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="flex items-center gap-2.5"
        >
          <div className="w-9 h-9 bg-[#C8FF00] flex items-center justify-center">
            <Cctv className="w-5 h-5 text-black" strokeWidth={2.5} />
          </div>
          <div>
            <div className="font-display text-base font-bold tracking-tighter">SmartCam</div>
            <div className="text-[10px] uppercase tracking-[0.25em] text-gray-500 font-mono">SaaS · 2026</div>
          </div>
        </motion.div>
      </div>

      <nav className="flex-1 px-3 py-5 space-y-0.5 overflow-y-auto">
        {nav.map((n, i) => (
          <NavRow key={n.to} idx={i} to={n.to} label={n.label} Icon={n.icon} testid={n.testid} />
        ))}

        {user?.role === "super_admin" && (
          <>
            <div className="pt-6 pb-2 px-3 text-[10px] uppercase tracking-[0.25em] text-gray-600 font-mono">
              Plataforma
            </div>
            <NavRow idx={nav.length} to="/admin" label="Super Admin" Icon={Shield} testid="nav-admin" />
          </>
        )}
      </nav>

      <div className="px-3 py-4 border-t border-white/10">
        <div className="flex items-center gap-3 px-2 py-2">
          <div className="w-8 h-8 bg-[#C8FF00] flex items-center justify-center text-xs font-bold uppercase text-black">
            {user?.name?.[0] || "U"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate" data-testid="sidebar-user-name">{user?.name}</div>
            <div className="text-[11px] text-gray-500 truncate font-mono">{user?.email}</div>
          </div>
          <button
            data-testid="sidebar-logout-button"
            onClick={onLogout}
            className="p-2 text-gray-400 hover:text-[#C8FF00] hover:bg-white/5 transition-colors"
            title="Cerrar sesión"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
