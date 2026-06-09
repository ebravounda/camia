import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Cctv, Cpu, AlertTriangle, ShieldAlert, Radio, ArrowRight, Plus } from "lucide-react";

const StatCard = ({ icon: Icon, label, value, accent = "blue", testid }) => {
  const accents = {
    blue: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    amber: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    red: "text-red-400 bg-red-500/10 border-red-500/20",
    green: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  };
  return (
    <div data-testid={testid} className="p-5 rounded-xl bg-[#12141D] border border-white/10 hover:border-white/20 transition-colors">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500 font-mono">{label}</div>
          <div className="font-display text-3xl font-semibold mt-2">{value}</div>
        </div>
        <div className={`w-9 h-9 rounded-lg border flex items-center justify-center ${accents[accent]}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
    </div>
  );
};

const LiveTile = ({ camera, index }) => {
  if (!camera) {
    return (
      <div className="relative aspect-video rounded-lg bg-black border border-white/10 overflow-hidden group" data-testid={`live-tile-${index}`}>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(59,130,246,0.08),transparent_70%)]" />
        <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600">
          <Cctv className="w-10 h-10 mb-2 opacity-40" />
          <div className="text-xs font-mono uppercase tracking-widest">Sin cámara · slot {index}</div>
          <div className="text-[10px] text-gray-700 mt-1">Empareja tu Raspberry para activar</div>
        </div>
        <div className="absolute top-3 left-3 flex items-center gap-2 px-2 py-1 rounded-md bg-black/60 border border-white/10 text-[10px] font-mono uppercase tracking-widest">
          <span className="w-1.5 h-1.5 rounded-full bg-gray-600" />
          OFFLINE
        </div>
      </div>
    );
  }
  const isLive = camera.status === "live";
  return (
    <div className="relative aspect-video rounded-lg bg-black border border-white/10 overflow-hidden group" data-testid={`live-tile-${index}`}>
      {camera.last_thumbnail ? (
        <img src={`data:image/jpeg;base64,${camera.last_thumbnail}`} alt={camera.name} className="w-full h-full object-cover" />
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600">
          <Cctv className="w-10 h-10 mb-2 opacity-40" />
          <div className="text-xs font-mono uppercase tracking-widest">{camera.name}</div>
          <div className="text-[10px] text-gray-700 mt-1">Esperando primer frame...</div>
        </div>
      )}
      <div className={`absolute top-3 left-3 flex items-center gap-2 px-2 py-1 rounded-md bg-black/60 border border-white/10 text-[10px] font-mono uppercase tracking-widest ${
        isLive ? "text-emerald-400" : "text-gray-400"
      }`}>
        {isLive && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 live-dot" />}
        {isLive ? "LIVE" : "OFFLINE"}
      </div>
      <div className="absolute bottom-3 left-3 px-2 py-1 rounded-md bg-black/60 border border-white/10 text-[10px] font-mono">
        {camera.name}
      </div>
    </div>
  );
};

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [cameras, setCameras] = useState([]);

  useEffect(() => {
    const load = async () => {
      try {
        const [s, e, c] = await Promise.all([
          api.get("/dashboard/stats"),
          api.get("/events", { params: { limit: 8 } }),
          api.get("/cameras"),
        ]);
        setStats(s.data);
        setEvents(e.data || []);
        setCameras(c.data || []);
      } catch (err) { /* ignore */ }
    };
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <AppShell
      title={`Hola, ${user?.name?.split(" ")[0] || "usuario"}`}
      subtitle="Centro de control · monitoreo en tiempo real"
      action={
        <Link to="/devices" data-testid="dashboard-add-device-cta">
          <Button className="bg-blue-600 hover:bg-blue-700 shadow-[0_0_14px_rgba(37,99,235,0.35)]">
            <Plus className="w-4 h-4 mr-1.5" /> Vincular Raspberry
          </Button>
        </Link>
      }
    >
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard testid="stat-devices" icon={Cpu} label="Raspberrys" value={stats?.devices_count ?? "—"} accent="blue" />
        <StatCard testid="stat-cameras" icon={Cctv} label="Cámaras" value={stats?.cameras_count ?? "—"} accent="green" />
        <StatCard testid="stat-events" icon={AlertTriangle} label="Eventos 24h" value={stats?.events_24h ?? "—"} accent="amber" />
        <StatCard testid="stat-suspicious" icon={ShieldAlert} label="Sospechosos 24h" value={stats?.suspicious_24h ?? "—"} accent="red" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live grid */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500 font-mono">Cámaras en vivo</div>
              <h2 className="font-display text-xl font-semibold mt-1">Grid 2×2</h2>
            </div>
            <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-gray-500">
              <Radio className="w-3 h-3 text-blue-400" /> Streaming en Fase 3
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[0, 1, 2, 3].map((i) => <LiveTile key={i} index={i + 1} camera={cameras[i]} />)}
          </div>
        </div>

        {/* Events timeline */}
        <div className="lg:col-span-1">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500 font-mono">Línea de tiempo</div>
              <h2 className="font-display text-xl font-semibold mt-1">Eventos recientes</h2>
            </div>
            <Link to="/events" className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1" data-testid="dashboard-events-link">
              Ver todos <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="rounded-xl bg-[#12141D] border border-white/10 divide-y divide-white/5">
            {events.length === 0 && (
              <div className="p-6 text-center text-sm text-gray-500" data-testid="dashboard-events-empty">
                Aún no hay eventos. Vincula tu Raspberry y configura cámaras para empezar.
              </div>
            )}
            {events.map((ev) => (
              <div key={ev.id} className="p-3 hover:bg-white/5 transition-colors flex gap-3 items-start cursor-pointer border-l-2 border-transparent hover:border-blue-500">
                <div className="w-9 h-9 rounded-md bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{ev.event_type}</div>
                  <div className="text-[11px] text-gray-500 font-mono">{ev.camera_name || ev.camera_id}</div>
                </div>
                <div className="text-[10px] text-gray-500 font-mono shrink-0">
                  {new Date(ev.created_at).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
