import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import AppShell from "@/components/AppShell";
import api from "@/lib/api";
import { AlertTriangle, Filter, User, Car, Dog, Activity, ShieldAlert, EyeOff, Film } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const TYPE_META = {
  person: { icon: User, color: "text-[#C8FF00] bg-[#C8FF00]/10 border-[#C8FF00]/30", label: "Persona" },
  unknown_face: { icon: EyeOff, color: "text-amber-300 bg-amber-500/10 border-amber-400/30", label: "Cara desconocida" },
  animal: { icon: Dog, color: "text-emerald-300 bg-emerald-500/10 border-emerald-400/30", label: "Animal" },
  vehicle: { icon: Car, color: "text-sky-300 bg-sky-500/10 border-sky-400/30", label: "Vehículo" },
  motion: { icon: Activity, color: "text-gray-300 bg-white/5 border-white/15", label: "Movimiento" },
  suspicious: { icon: ShieldAlert, color: "text-red-400 bg-red-500/10 border-red-500/30", label: "Sospechoso" },
};

const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  show: (i) => ({ opacity: 1, y: 0, transition: { delay: Math.min(i * 0.025, 0.4), duration: 0.25, ease: [0.22, 1, 0.36, 1] } }),
};

export default function Events() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState(null);

  const load = async (type = "") => {
    setLoading(true);
    try {
      const params = type ? { event_type: type, limit: 100 } : { limit: 100 };
      const { data } = await api.get("/events", { params });
      setEvents(data || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    const id = setInterval(() => load(filter), 15000);
    return () => clearInterval(id);
  }, [filter]);

  const apply = (t) => { setFilter(t); load(t); };

  return (
    <AppShell title="Eventos" subtitle="Timeline de detecciones · micro-clips de 5s">
      <div className="flex flex-wrap items-center gap-2 mb-6">
        <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-gray-500 mr-2">
          <Filter className="w-3 h-3" /> Filtrar
        </div>
        {["", "person", "unknown_face", "suspicious", "animal", "vehicle", "motion"].map((t) => (
          <Button
            key={t || "all"}
            data-testid={`event-filter-${t || "all"}`}
            variant="outline"
            size="sm"
            onClick={() => apply(t)}
            className={`h-8 rounded-none border transition-all ${
              filter === t
                ? "bg-[#C8FF00] text-black border-[#C8FF00] font-semibold"
                : "bg-white/5 text-gray-300 border-white/10 hover:bg-white/10 hover:border-white/20"
            }`}
          >
            {t === "" ? "Todos" : (TYPE_META[t]?.label || t)}
          </Button>
        ))}
      </div>

      <div className="bg-[#0F0F0F] border border-white/10 divide-y divide-white/5">
        {loading && events.length === 0 && (
          <div className="p-6 text-sm text-gray-500 font-mono">Cargando timeline...</div>
        )}
        {!loading && events.length === 0 && (
          <div data-testid="events-empty" className="p-12 text-center">
            <AlertTriangle className="w-10 h-10 mx-auto text-gray-600 mb-3" />
            <h3 className="font-display text-lg font-semibold">Sin eventos aún</h3>
            <p className="text-sm text-gray-400 mt-2 max-w-md mx-auto">
              Los eventos y sus micro-clips de 5s aparecerán aquí cuando la IA detecte algo en tus cámaras.
            </p>
          </div>
        )}
        <AnimatePresence initial={false}>
          {events.map((ev, idx) => {
            const meta = TYPE_META[ev.event_type] || TYPE_META.motion;
            return (
              <motion.div
                key={ev.id}
                custom={idx}
                variants={fadeUp}
                initial="hidden"
                animate="show"
                exit={{ opacity: 0 }}
                whileHover={{ x: 4 }}
                data-testid={`event-row-${ev.id}`}
                onClick={() => setSelected(ev)}
                className="p-4 hover:bg-white/[0.04] transition-colors flex gap-4 items-center cursor-pointer border-l-2 border-transparent hover:border-[#C8FF00]"
              >
                <div className={`w-10 h-10 border flex items-center justify-center ${meta.color}`}>
                  <meta.icon className="w-4 h-4" />
                </div>
                <div className="relative w-20 h-12 bg-black border border-white/10 flex items-center justify-center text-[10px] text-gray-600 font-mono shrink-0 overflow-hidden">
                  {ev.thumbnail_url
                    ? <img src={ev.thumbnail_url} alt="" className="w-full h-full object-cover" />
                    : "preview"}
                  {ev.clip_url && (
                    <span className="absolute bottom-0.5 right-0.5 px-1 bg-[#C8FF00] text-black text-[8px] font-bold leading-tight">
                      CLIP
                    </span>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm">{meta.label}</div>
                  <div className="text-xs text-gray-500 mt-0.5 truncate">{ev.description || ev.camera_name || ev.camera_id}</div>
                </div>
                <div className={`text-[10px] px-2 py-0.5 uppercase font-mono tracking-widest ${
                  ev.severity === "high" ? "text-red-400 bg-red-500/10 border border-red-500/20"
                    : ev.severity === "medium" ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
                    : "text-gray-400 bg-white/5 border border-white/10"
                }`}>{ev.severity}</div>
                <div className="text-xs text-gray-500 font-mono shrink-0 hidden sm:block">
                  {new Date(ev.created_at).toLocaleString("es-ES", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* Event detail modal with video player */}
      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="bg-[#0F0F0F] border border-white/10 text-white max-w-3xl p-0 overflow-hidden rounded-none">
          {selected && (() => {
            const meta = TYPE_META[selected.event_type] || TYPE_META.motion;
            const fullClip = selected.clip_url ? `${BACKEND}${selected.clip_url}` : null;
            return (
              <>
                <DialogHeader className="px-6 py-5 border-b border-white/10">
                  <DialogTitle className="font-display flex items-center gap-3" data-testid="event-modal-title">
                    <span className={`w-9 h-9 border flex items-center justify-center ${meta.color}`}>
                      <meta.icon className="w-4 h-4" />
                    </span>
                    <div>
                      <div className="text-base">{meta.label}</div>
                      <div className="text-xs text-gray-500 font-normal font-mono mt-0.5">
                        {selected.camera_name || selected.camera_id} ·{" "}
                        {new Date(selected.created_at).toLocaleString("es-ES")}
                      </div>
                    </div>
                  </DialogTitle>
                </DialogHeader>
                <div className="p-6 space-y-4">
                  {fullClip ? (
                    <div className="bg-black border border-white/10 overflow-hidden">
                      <video
                        key={fullClip}
                        src={fullClip}
                        controls
                        autoPlay
                        loop
                        playsInline
                        muted
                        className="w-full max-h-[60vh] object-contain bg-black"
                        data-testid="event-modal-clip"
                      />
                      <div className="flex items-center gap-2 px-3 py-2 border-t border-white/10 text-[10px] font-mono uppercase tracking-widest text-[#C8FF00]">
                        <Film className="w-3 h-3" /> Micro-clip · 5s · MP4
                      </div>
                    </div>
                  ) : selected.thumbnail_url ? (
                    <div className="relative bg-black border border-white/10 overflow-hidden">
                      <img
                        src={selected.thumbnail_url}
                        alt={meta.label}
                        className="w-full max-h-[60vh] object-contain"
                        data-testid="event-modal-thumbnail"
                      />
                      <div className="absolute bottom-2 right-2 px-2 py-1 bg-black/70 border border-white/10 text-[10px] font-mono uppercase tracking-widest text-gray-400">
                        Clip generándose...
                      </div>
                    </div>
                  ) : (
                    <div className="aspect-video bg-black border border-white/10 flex items-center justify-center text-gray-500 text-sm">
                      Sin miniatura
                    </div>
                  )}

                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-white/5 border border-white/10 p-3">
                      <div className="text-[10px] uppercase tracking-widest font-mono text-gray-500">Tipo</div>
                      <div className="text-sm mt-1 capitalize">{meta.label}</div>
                    </div>
                    <div className="bg-white/5 border border-white/10 p-3">
                      <div className="text-[10px] uppercase tracking-widest font-mono text-gray-500">Severidad</div>
                      <div className={`text-sm mt-1 capitalize ${
                        selected.severity === "high" ? "text-red-400"
                          : selected.severity === "medium" ? "text-amber-400" : "text-gray-300"
                      }`}>{selected.severity}</div>
                    </div>
                    <div className="bg-white/5 border border-white/10 p-3">
                      <div className="text-[10px] uppercase tracking-widest font-mono text-gray-500">Cámara</div>
                      <div className="text-sm mt-1 truncate">{selected.camera_name || "—"}</div>
                    </div>
                  </div>

                  {selected.description && (
                    <div className="bg-white/5 border border-white/10 p-3">
                      <div className="text-[10px] uppercase tracking-widest font-mono text-gray-500 mb-1">Descripción</div>
                      <div className="text-sm text-gray-200">{selected.description}</div>
                    </div>
                  )}

                  <div className="bg-[#0A0A0A] border border-white/10 p-3 text-[11px] font-mono text-gray-500 break-all">
                    event_id: {selected.id}
                  </div>
                </div>
              </>
            );
          })()}
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
