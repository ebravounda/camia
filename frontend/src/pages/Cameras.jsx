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
import { Cctv, Plus, Trash2, Play, Volume2, VolumeX } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";

const RES_OPTIONS = [
  { value: "SD",  label: "SD · 640×480",   hint: "Bajo consumo" },
  { value: "HD",  label: "HD · 1280×720",  hint: "Recomendado" },
  { value: "FHD", label: "FHD · 1920×1080", hint: "Máxima calidad" },
];

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

  const updateSetting = async (id, patch) => {
    // Optimistic local update so UI feels fluid
    setCameras((cs) => cs.map((c) => (c.id === id ? { ...c, ...patch } : c)));
    try {
      await api.patch(`/cameras/${id}`, patch);
      toast.success("Ajuste guardado · el agente lo aplicará en segundos");
    } catch (e) {
      toast.error(formatApiError(e));
      fetchAll();
    }
  };

  return (
    <AppShell
      title="Cámaras"
      subtitle="Gestiona resolución y audio · HD/FHD por cámara"
      action={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button
              data-testid="cameras-add-button"
              className="bg-[#C8FF00] hover:bg-[#B8EF00] text-black font-semibold rounded-none border border-[#C8FF00]"
              disabled={devices.length === 0}
            >
              <Plus className="w-4 h-4 mr-1.5" /> Nueva cámara
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#0F0F0F] border border-white/10 text-white rounded-none">
            <DialogHeader>
              <DialogTitle className="font-display">Añadir cámara USB</DialogTitle>
              <DialogDescription className="text-gray-400">
                Hasta 4 cámaras por Raspberry Pi.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={create} className="space-y-4">
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-widest font-mono text-gray-400">Nombre</Label>
                <Input data-testid="camera-name-input" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej. Entrada principal" className="bg-[#0A0A0A] border-white/10 h-11 rounded-none" />
              </div>
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-widest font-mono text-gray-400">Raspberry Pi</Label>
                <Select value={deviceId} onValueChange={setDeviceId}>
                  <SelectTrigger data-testid="camera-device-select" className="bg-[#0A0A0A] border-white/10 h-11 rounded-none">
                    <SelectValue placeholder="Seleccionar dispositivo" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0F0F0F] border-white/10 text-white rounded-none">
                    {devices.map((d) => (
                      <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-widest font-mono text-gray-400">Índice USB (/dev/video*)</Label>
                <Input data-testid="camera-usb-input" type="number" min="0" max="9" value={usbIndex} onChange={(e) => setUsbIndex(e.target.value)} className="bg-[#0A0A0A] border-white/10 h-11 rounded-none" />
              </div>
              <DialogFooter>
                <Button type="submit" data-testid="camera-submit-button" disabled={submitting} className="bg-[#C8FF00] hover:bg-[#B8EF00] text-black font-semibold rounded-none">
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
        <div data-testid="cameras-no-device" className="bg-[#0F0F0F] border border-white/10 p-12 text-center">
          <Cctv className="w-10 h-10 mx-auto text-gray-600 mb-3" />
          <h3 className="font-display text-lg font-semibold">Primero registra una Raspberry</h3>
          <p className="text-sm text-gray-400 mt-2">Necesitas al menos un dispositivo antes de añadir cámaras.</p>
        </div>
      ) : cameras.length === 0 ? (
        <div data-testid="cameras-empty" className="bg-[#0F0F0F] border border-white/10 p-12 text-center">
          <Cctv className="w-10 h-10 mx-auto text-gray-600 mb-3" />
          <h3 className="font-display text-lg font-semibold">Aún no hay cámaras</h3>
          <p className="text-sm text-gray-400 mt-2">Añade hasta 4 cámaras USB por Raspberry.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cameras.map((c) => {
            const device = devices.find((d) => d.id === c.device_id);
            const audioOn = c.audio_enabled !== false;
            return (
              <div key={c.id} data-testid={`camera-card-${c.id}`} className="bg-[#0F0F0F] border border-white/10 overflow-hidden hover:border-[#C8FF00]/40 transition-colors">
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
                  <div className={`absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 bg-black/60 border border-white/10 text-[10px] font-mono uppercase tracking-widest ${
                    c.status === "live" ? "text-[#C8FF00]" : "text-gray-400"
                  }`}>
                    {c.status === "live" && <span className="w-1.5 h-1.5 bg-[#C8FF00] live-dot animate-pulse" />}
                    {c.status === "live" ? "LIVE" : "OFFLINE"}
                  </div>
                  <div className="absolute top-3 right-3 px-2 py-1 bg-black/60 border border-white/10 text-[10px] font-mono uppercase tracking-widest text-[#C8FF00]">
                    {c.resolution || "HD"}
                  </div>
                </div>
                <div className="p-4 space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-display font-semibold truncate">{c.name}</div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Link to={`/cameras/${c.id}/live`} data-testid={`camera-live-${c.id}`}>
                        <button className="p-1.5 text-[#C8FF00] hover:bg-[#C8FF00]/10 transition-colors" title="Ver en vivo">
                          <Play className="w-3.5 h-3.5" />
                        </button>
                      </Link>
                      <button onClick={() => remove(c.id)} className="p-1.5 hover:bg-red-500/10 text-gray-400 hover:text-red-400 transition-colors" data-testid={`camera-delete-${c.id}`}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 font-mono">/dev/video{c.usb_index} · {device?.name || "—"}</div>

                  {/* Resolution selector */}
                  <div>
                    <Label className="text-[10px] uppercase tracking-widest font-mono text-gray-500">Calidad</Label>
                    <div className="grid grid-cols-3 gap-1 mt-1.5">
                      {RES_OPTIONS.map((r) => {
                        const active = (c.resolution || "HD") === r.value;
                        return (
                          <button
                            key={r.value}
                            data-testid={`camera-res-${c.id}-${r.value}`}
                            onClick={() => updateSetting(c.id, { resolution: r.value })}
                            className={`px-2 py-1.5 text-[10px] font-mono uppercase tracking-wider border transition-all ${
                              active
                                ? "bg-[#C8FF00] text-black border-[#C8FF00] font-bold"
                                : "bg-white/[0.03] text-gray-400 border-white/10 hover:border-white/20 hover:text-white"
                            }`}
                            title={r.hint}
                          >
                            {r.value}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Audio toggle */}
                  <button
                    data-testid={`camera-audio-${c.id}`}
                    onClick={() => updateSetting(c.id, { audio_enabled: !audioOn })}
                    className={`w-full flex items-center justify-between px-3 py-2 border transition-all ${
                      audioOn
                        ? "bg-[#C8FF00]/10 border-[#C8FF00]/30 text-[#C8FF00]"
                        : "bg-white/[0.03] border-white/10 text-gray-400 hover:text-white"
                    }`}
                  >
                    <span className="text-[10px] font-mono uppercase tracking-wider">Audio</span>
                    {audioOn ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
