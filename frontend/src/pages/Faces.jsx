import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import api from "@/lib/api";
import { ScanFace, AlertTriangle } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

export default function Faces() {
  const [faces, setFaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  const load = async () => {
    try {
      const { data } = await api.get("/events", { params: { event_type: "unknown_face", limit: 200 } });
      setFaces(data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  return (
    <AppShell
      title="Caras detectadas"
      subtitle="Galería de rostros capturados por la IA del agente"
    >
      {loading ? (
        <div className="text-sm text-gray-500">Cargando...</div>
      ) : faces.length === 0 ? (
        <div data-testid="faces-empty" className="rounded-xl bg-[#12141D] border border-white/10 p-12 text-center">
          <ScanFace className="w-10 h-10 mx-auto text-gray-600 mb-3" />
          <h3 className="font-display text-lg font-semibold">Sin caras aún</h3>
          <p className="text-sm text-gray-400 mt-2 max-w-md mx-auto">
            Cuando el agente detecte una cara delante de la cámara, aparecerá aquí con su foto y timestamp.
            Asegúrate de que tu cara esté bien iluminada y mire a la cámara.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {faces.map((f) => (
            <div
              key={f.id}
              data-testid={`face-card-${f.id}`}
              onClick={() => setSelected(f)}
              className="group rounded-xl bg-[#12141D] border border-white/10 hover:border-blue-500/40 overflow-hidden cursor-pointer transition-all hover:shadow-[0_0_18px_rgba(59,130,246,0.18)]"
            >
              <div className="aspect-square bg-black overflow-hidden">
                {f.thumbnail_url ? (
                  <img src={f.thumbnail_url} alt="face" className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-700">
                    <ScanFace className="w-10 h-10" />
                  </div>
                )}
              </div>
              <div className="p-3">
                <div className="text-xs font-medium truncate">{f.camera_name || "—"}</div>
                <div className="text-[10px] text-gray-500 font-mono mt-1">
                  {new Date(f.created_at).toLocaleString("es-ES", {
                    day: "2-digit", month: "2-digit",
                    hour: "2-digit", minute: "2-digit",
                  })}
                </div>
                <div className="mt-2 inline-block px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-widest bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  Desconocida
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="bg-[#12141D] border-white/10 text-white max-w-xl p-0 overflow-hidden">
          {selected && (
            <>
              <DialogHeader className="px-6 py-5 border-b border-white/10">
                <DialogTitle className="font-display flex items-center gap-3">
                  <span className="w-9 h-9 rounded-md bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                    <ScanFace className="w-4 h-4 text-amber-400" />
                  </span>
                  <div>
                    <div className="text-base">Cara desconocida</div>
                    <div className="text-xs text-gray-500 font-normal font-mono mt-0.5">
                      {selected.camera_name} · {new Date(selected.created_at).toLocaleString("es-ES")}
                    </div>
                  </div>
                </DialogTitle>
              </DialogHeader>
              <div className="p-6">
                {selected.thumbnail_url && (
                  <div className="rounded-lg bg-black border border-white/10 overflow-hidden">
                    <img src={selected.thumbnail_url} alt="face" className="w-full max-h-[60vh] object-contain" />
                  </div>
                )}
                {selected.description && (
                  <div className="mt-4 text-sm text-gray-300">{selected.description}</div>
                )}
                <div className="mt-4 rounded-md bg-amber-500/5 border border-amber-500/20 p-3 text-xs text-amber-200/80 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <div>
                    El reconocimiento facial (comparar contra tu galería de "caras conocidas") llegará en la siguiente iteración.
                    De momento, todas las caras detectadas aparecen como "Desconocida".
                  </div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
