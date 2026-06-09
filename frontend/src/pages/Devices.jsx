import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Cpu, Plus, Copy, RefreshCw, Trash2, Wifi, WifiOff, Download, Thermometer, Activity, Globe } from "lucide-react";
import { toast } from "sonner";

export default function Devices() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchDevices = async () => {
    try {
      const { data } = await api.get("/devices");
      setDevices(data || []);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDevices(); }, []);

  const create = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/devices", { name, location });
      toast.success("Raspberry registrada");
      setName(""); setLocation(""); setOpen(false);
      fetchDevices();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  const regenerate = async (id) => {
    try {
      await api.post(`/devices/${id}/regenerate-token`);
      toast.success("Token regenerado");
      fetchDevices();
    } catch (e) { toast.error(formatApiError(e)); }
  };

  const remove = async (id) => {
    if (!window.confirm("¿Eliminar este dispositivo? Las cámaras vinculadas también se eliminarán.")) return;
    try {
      await api.delete(`/devices/${id}`);
      toast.success("Dispositivo eliminado");
      fetchDevices();
    } catch (e) { toast.error(formatApiError(e)); }
  };

  const copy = (token) => {
    navigator.clipboard.writeText(token);
    toast.success("Token copiado");
  };

  const downloadAgent = async () => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const token = localStorage.getItem("sc_access_token");
      const res = await fetch(`${BACKEND_URL}/api/agent/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      });
      if (!res.ok) throw new Error("No se pudo descargar");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "smartcam-agent.tar.gz";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Agente descargado");
    } catch (e) {
      toast.error("Error al descargar el agente");
    }
  };

  return (
    <AppShell
      title="Raspberry Pi"
      subtitle="Vincula tus dispositivos usando tokens de emparejamiento"
      action={
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={downloadAgent}
            data-testid="devices-download-agent-button"
            className="bg-white/5 border-white/15 text-white hover:bg-white/10"
          >
            <Download className="w-4 h-4 mr-1.5" /> Descargar agente
          </Button>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="devices-add-button" className="bg-blue-600 hover:bg-blue-700 shadow-[0_0_14px_rgba(37,99,235,0.35)]">
              <Plus className="w-4 h-4 mr-1.5" /> Nueva Raspberry
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#12141D] border-white/10 text-white">
            <DialogHeader>
              <DialogTitle className="font-display">Registrar Raspberry Pi</DialogTitle>
              <DialogDescription className="text-gray-400">
                Recibirás un token de emparejamiento de 12 caracteres.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={create} className="space-y-4">
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-widest font-mono text-gray-400">Nombre</Label>
                <Input data-testid="device-name-input" required value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="Ej. Pi - Tienda Centro" className="bg-[#090A0F] border-white/10 h-11" />
              </div>
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-widest font-mono text-gray-400">Ubicación</Label>
                <Input data-testid="device-location-input" value={location} onChange={(e) => setLocation(e.target.value)}
                  placeholder="Ej. C/ Mayor 12, Madrid" className="bg-[#090A0F] border-white/10 h-11" />
              </div>
              <DialogFooter>
                <Button type="submit" data-testid="device-submit-button" disabled={submitting} className="bg-blue-600 hover:bg-blue-700">
                  {submitting ? "Creando..." : "Crear"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
        </div>
      }
    >
      {loading ? (
        <div className="text-sm text-gray-500">Cargando...</div>
      ) : devices.length === 0 ? (
        <div data-testid="devices-empty" className="rounded-xl bg-[#12141D] border border-white/10 p-12 text-center">
          <Cpu className="w-10 h-10 mx-auto text-gray-600 mb-3" />
          <h3 className="font-display text-lg font-semibold">Aún no tienes Raspberrys</h3>
          <p className="text-sm text-gray-400 mt-2 max-w-md mx-auto">
            Registra tu primer dispositivo para obtener un token de emparejamiento. Después instala el agente Python en tu Pi y úsalo para vincularla.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {devices.map((d) => (
            <div key={d.id} data-testid={`device-card-${d.id}`} className="rounded-xl bg-[#12141D] border border-white/10 p-5 hover:border-white/20 transition-colors">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                    <Cpu className="w-5 h-5 text-blue-400" />
                  </div>
                  <div>
                    <div className="font-display font-semibold">{d.name}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{d.location || "—"}</div>
                  </div>
                </div>
                <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-mono uppercase tracking-widest border ${
                  d.status === "online"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-white/5 text-gray-500 border-white/10"
                }`}>
                  {d.status === "online" ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                  {d.status}
                </div>
              </div>

              <div className="mt-5 rounded-lg bg-[#090A0F] border border-white/10 p-3">
                <div className="text-[10px] uppercase tracking-widest text-gray-500 font-mono mb-1">Token de emparejamiento</div>
                <div className="flex items-center justify-between gap-2">
                  <code className="font-mono text-sm text-blue-300 truncate" data-testid={`device-token-${d.id}`}>{d.pairing_token}</code>
                  <button onClick={() => copy(d.pairing_token)} className="p-1.5 rounded hover:bg-white/10 text-gray-400 hover:text-white" data-testid={`device-copy-${d.id}`}>
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {d.is_paired && (
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <div className="rounded-md bg-white/5 border border-white/10 p-2">
                    <div className="text-[9px] uppercase tracking-widest font-mono text-gray-500 flex items-center gap-1"><Thermometer className="w-2.5 h-2.5" /> CPU °C</div>
                    <div className="text-sm font-mono mt-0.5">{d.cpu_temp != null ? `${d.cpu_temp}°` : "—"}</div>
                  </div>
                  <div className="rounded-md bg-white/5 border border-white/10 p-2">
                    <div className="text-[9px] uppercase tracking-widest font-mono text-gray-500 flex items-center gap-1"><Activity className="w-2.5 h-2.5" /> CPU %</div>
                    <div className="text-sm font-mono mt-0.5">{d.cpu_usage != null ? `${d.cpu_usage}%` : "—"}</div>
                  </div>
                  <div className="rounded-md bg-white/5 border border-white/10 p-2">
                    <div className="text-[9px] uppercase tracking-widest font-mono text-gray-500 flex items-center gap-1"><Globe className="w-2.5 h-2.5" /> IP</div>
                    <div className="text-xs font-mono mt-0.5 truncate">{d.ip_address || "—"}</div>
                  </div>
                </div>
              )}

              <div className="mt-4 flex items-center justify-between">
                <div className="text-[11px] text-gray-500 font-mono">
                  Estado: <span className={d.is_paired ? "text-emerald-400" : "text-amber-400"}>{d.is_paired ? "vinculada" : "pendiente"}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" onClick={() => regenerate(d.id)} className="bg-white/5 border-white/15 text-white hover:bg-white/10 h-8" data-testid={`device-regen-${d.id}`}>
                    <RefreshCw className="w-3 h-3 mr-1.5" /> Regenerar
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => remove(d.id)} className="bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20 h-8" data-testid={`device-delete-${d.id}`}>
                    <Trash2 className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
