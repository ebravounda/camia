import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import api from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Users, Cpu, Cctv, AlertTriangle, CreditCard, UserCheck } from "lucide-react";
import { toast } from "sonner";

const StatCard = ({ icon: Icon, label, value, testid }) => (
  <div data-testid={testid} className="p-5 rounded-xl bg-[#12141D] border border-white/10">
    <div className="flex items-start justify-between">
      <div>
        <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500 font-mono">{label}</div>
        <div className="font-display text-3xl font-semibold mt-2">{value}</div>
      </div>
      <div className="w-9 h-9 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
        <Icon className="w-4 h-4 text-blue-400" />
      </div>
    </div>
  </div>
);

export default function AdminPanel() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [devices, setDevices] = useState([]);

  const load = async () => {
    try {
      const [s, u, d] = await Promise.all([
        api.get("/admin/stats"),
        api.get("/admin/users"),
        api.get("/admin/devices"),
      ]);
      setStats(s.data);
      setUsers(u.data || []);
      setDevices(d.data || []);
    } catch (e) {
      toast.error("Error al cargar datos de admin");
    }
  };

  useEffect(() => { load(); }, []);

  const toggleUser = async (id) => {
    try {
      await api.patch(`/admin/users/${id}/toggle-active`);
      toast.success("Estado actualizado");
      load();
    } catch (e) { toast.error("Error"); }
  };

  return (
    <AppShell title="Super Admin" subtitle="Panel global de la plataforma">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        <StatCard testid="admin-stat-users" icon={Users} label="Usuarios" value={stats?.total_users ?? "—"} />
        <StatCard testid="admin-stat-active" icon={UserCheck} label="Activos" value={stats?.active_users ?? "—"} />
        <StatCard testid="admin-stat-devices" icon={Cpu} label="Raspberrys" value={stats?.total_devices ?? "—"} />
        <StatCard testid="admin-stat-cameras" icon={Cctv} label="Cámaras" value={stats?.total_cameras ?? "—"} />
        <StatCard testid="admin-stat-paid" icon={CreditCard} label="Pagos activos" value={stats?.paid_subscriptions ?? "—"} />
      </div>

      <div className="grid grid-cols-1 gap-6">
        <div className="rounded-xl bg-[#12141D] border border-white/10 overflow-hidden">
          <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between">
            <h2 className="font-display text-lg font-semibold">Usuarios</h2>
            <span className="text-[10px] font-mono uppercase tracking-widest text-gray-500">{users.length} cuentas</span>
          </div>
          <Table>
            <TableHeader>
              <TableRow className="border-white/10 hover:bg-transparent">
                <TableHead className="text-gray-400 text-[10px] uppercase tracking-widest font-mono">Email</TableHead>
                <TableHead className="text-gray-400 text-[10px] uppercase tracking-widest font-mono">Nombre</TableHead>
                <TableHead className="text-gray-400 text-[10px] uppercase tracking-widest font-mono">Rol</TableHead>
                <TableHead className="text-gray-400 text-[10px] uppercase tracking-widest font-mono">Plan</TableHead>
                <TableHead className="text-gray-400 text-[10px] uppercase tracking-widest font-mono">Estado</TableHead>
                <TableHead className="text-gray-400 text-[10px] uppercase tracking-widest font-mono text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id} data-testid={`admin-user-row-${u.id}`} className="border-white/10 hover:bg-white/5">
                  <TableCell className="text-gray-200 font-mono text-xs">{u.email}</TableCell>
                  <TableCell className="text-gray-300">{u.name}</TableCell>
                  <TableCell>
                    <Badge className={u.role === "super_admin"
                      ? "bg-blue-500/15 text-blue-300 border border-blue-500/30"
                      : "bg-white/5 text-gray-300 border border-white/10"}>
                      {u.role}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-gray-300 capitalize">{u.subscription_plan}</TableCell>
                  <TableCell>
                    <Badge className={u.is_active
                      ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                      : "bg-red-500/15 text-red-400 border border-red-500/30"}>
                      {u.is_active ? "Activo" : "Bloqueado"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      data-testid={`admin-toggle-user-${u.id}`}
                      size="sm"
                      variant="outline"
                      onClick={() => toggleUser(u.id)}
                      disabled={u.role === "super_admin"}
                      className="bg-white/5 border-white/15 text-white hover:bg-white/10 h-8"
                    >
                      {u.is_active ? "Desactivar" : "Activar"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <div className="rounded-xl bg-[#12141D] border border-white/10 overflow-hidden">
          <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between">
            <h2 className="font-display text-lg font-semibold">Dispositivos globales</h2>
            <span className="text-[10px] font-mono uppercase tracking-widest text-gray-500">{devices.length} raspberrys</span>
          </div>
          <Table>
            <TableHeader>
              <TableRow className="border-white/10 hover:bg-transparent">
                <TableHead className="text-gray-400 text-[10px] uppercase tracking-widest font-mono">Nombre</TableHead>
                <TableHead className="text-gray-400 text-[10px] uppercase tracking-widest font-mono">Ubicación</TableHead>
                <TableHead className="text-gray-400 text-[10px] uppercase tracking-widest font-mono">Estado</TableHead>
                <TableHead className="text-gray-400 text-[10px] uppercase tracking-widest font-mono">Vinculado</TableHead>
                <TableHead className="text-gray-400 text-[10px] uppercase tracking-widest font-mono">Owner</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {devices.length === 0 && (
                <TableRow><TableCell colSpan={5} className="text-center text-gray-500 py-8">Sin dispositivos registrados</TableCell></TableRow>
              )}
              {devices.map((d) => (
                <TableRow key={d.id} data-testid={`admin-device-row-${d.id}`} className="border-white/10 hover:bg-white/5">
                  <TableCell className="text-gray-200">{d.name}</TableCell>
                  <TableCell className="text-gray-400">{d.location || "—"}</TableCell>
                  <TableCell>
                    <Badge className="bg-white/5 text-gray-300 border border-white/10 capitalize">{d.status}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge className={d.is_paired
                      ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                      : "bg-amber-500/15 text-amber-400 border border-amber-500/30"}>
                      {d.is_paired ? "sí" : "no"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-gray-400 font-mono text-xs">{d.user_id.slice(0, 8)}…</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </AppShell>
  );
}
