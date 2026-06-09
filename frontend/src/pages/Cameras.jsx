import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Cctv, Plus, Trash2, Play } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";

export default function Cameras() {
  const [cameras, setCameras] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [usbIndex, setUsbIndex] = useState("0");
  const [submitting, setSubmitting] = useState(false);

  const fetchAll = async () => {
    try {
      const [c, d] = await Promise.all([api.get("/cameras"), api.get("/devices")]);
      setCameras(c.data || []);
      setDevices(d.data || []);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const create = async (e) => {
    e.preventDefault();
    if (!deviceId) { toast.error("Selecciona un dispositivo"); return; }
    setSubmitting(true);
    try {
      await api.post("/cameras", { name, device_id: deviceId, usb_index: parseInt(usbIndex || "0", 10), enabled: true });
      toast.success("Cámara añadida");
      setName(""); setDeviceId(""); setUsbIndex("0"); setOpen(false);
      fetchAll();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("¿Eliminar cámara?")) return;
    try { await api.delete(`/cameras/${id}`); toast.success("Cámara eliminada"); fetchAll(); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  return (
    <AppShell
      title="Cámaras"
      subtitle="Gestiona las cámaras USB conectadas a tus Raspberrys"
      action={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="cameras-add-button" className="bg-blue-600 hover:bg-blue-700 shadow-[0_0_14px_rgba(37,99,235,0.35)]" disabled={devices.length === 0}>
              <Plus className="w-4 h-4 mr-1.5" /> Nueva cámara
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#12141D] border-white/10 text-white">
            <DialogHeader>
              <DialogTitle className="font-display">Añadir cámara USB</DialogTitle>
              <DialogDescription className="text-gray-400">
                Hasta 4 cámaras por Raspberry Pi.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={create} className="space-y-4">
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-widest font-mono text-gray-400">Nombre</Label>
                <Input data-testid="camera-name-input" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej. Entrada principal" className="bg-[#090A0F] border-white/10 h-11" />
              </div>
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-widest font-mono text-gray-400">Raspberry Pi</Label>
                <Select value={deviceId} onValueChange={setDeviceId}>
                  <SelectTrigger data-testid="camera-device-select" className="bg-[#090A0F] border-white/10 h-11">
                    <SelectValue placeholder="Seleccionar dispositivo" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#12141D] border-white/10 text-white">
                    {devices.map((d) => (
                      <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-widest font-mono text-gray-400">Índice USB (/dev/video*)</Label>
                <Input data-testid="camera-usb-input" type="number" min="0" max="9" value={usbIndex} onChange={(e) => setUsbIndex(e.target.value)} className="bg-[#090A0F] border-white/10 h-11" />
              </div>
              <DialogFooter>
                <Button type="submit" data-testid="camera-submit-button" disabled={submitting} className="bg-blue-600 hover:bg-blue-700">
                  {submitting ? "Añadiendo..." : "Añadir"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      }
    >
      {loading ? (
        <div className="text-sm text-gray-500">Cargando...</div>
      ) : devices.length === 0 ? (
        <div data-testid="cameras-no-device" className="rounded-xl bg-[#12141D] border border-white/10 p-12 text-center">
          <Cctv className="w-10 h-10 mx-auto text-gray-600 mb-3" />
          <h3 className="font-display text-lg font-semibold">Primero registra una Raspberry</h3>
          <p className="text-sm text-gray-400 mt-2">Necesitas al menos un dispositivo antes de añadir cámaras.</p>
        </div>
      ) : cameras.length === 0 ? (
        <div data-testid="cameras-empty" className="rounded-xl bg-[#12141D] border border-white/10 p-12 text-center">
          <Cctv className="w-10 h-10 mx-auto text-gray-600 mb-3" />
          <h3 className="font-display text-lg font-semibold">Aún no hay cámaras</h3>
          <p className="text-sm text-gray-400 mt-2">Añade hasta 4 cámaras USB por Raspberry.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cameras.map((c) => {
            const device = devices.find((d) => d.id === c.device_id);
            return (
              <div key={c.id} data-testid={`camera-card-${c.id}`} className="rounded-xl bg-[#12141D] border border-white/10 overflow-hidden">
                <div className="aspect-video bg-black flex items-center justify-center text-gray-700 relative overflow-hidden">
                  {c.last_thumbnail ? (
                    <img
                      src={`data:image/jpeg;base64,${c.last_thumbnail}`}
                      alt={c.name}
                      className="w-full h-full object-cover"
                      data-testid={`camera-thumb-${c.id}`}
                    />
                  ) : (
                    <Cctv className="w-10 h-10 opacity-40" />
                  )}
                  <div className={`absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-md bg-black/60 border border-white/10 text-[10px] font-mono uppercase tracking-widest ${
                    c.status === "live" ? "text-emerald-400" : "text-gray-400"
                  }`}>
                    {c.status === "live" && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 live-dot" />}
                    {c.status === "live" ? "LIVE" : "OFFLINE"}
                  </div>
                </div>
                <div className="p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-display font-semibold truncate">{c.name}</div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Link to={`/cameras/${c.id}/live`} data-testid={`camera-live-${c.id}`}>
                        <button className="p-1.5 rounded text-blue-400 hover:bg-blue-500/10 hover:text-blue-300 transition-colors" title="Ver en vivo">
                          <Play className="w-3.5 h-3.5" />
                        </button>
                      </Link>
                      <button onClick={() => remove(c.id)} className="p-1.5 rounded hover:bg-red-500/10 text-gray-400 hover:text-red-400" data-testid={`camera-delete-${c.id}`}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 mt-1 font-mono">/dev/video{c.usb_index} · {device?.name || "—"}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
