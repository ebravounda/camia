import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Radio, Maximize2, AlertTriangle } from "lucide-react";
import api from "@/lib/api";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function CameraLive() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [camera, setCamera] = useState(null);
  const [error, setError] = useState("");
  const [streamUrl, setStreamUrl] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/cameras");
        const cam = data.find((c) => c.id === id);
        if (!cam) { setError("Cámara no encontrada"); return; }
        setCamera(cam);
        // Use MJPEG multipart stream — browser displays it natively.
        // Cache buster ensures fresh connection on remount.
        setStreamUrl(`${BACKEND}/api/cameras/${id}/stream.mjpg?t=${Date.now()}`);
      } catch (e) { setError("Error cargando cámara"); }
    })();
  }, [id]);

  const goFullscreen = () => {
    const el = document.getElementById("live-stream-img");
    if (el?.requestFullscreen) el.requestFullscreen();
  };

  return (
    <AppShell
      title={camera ? `En vivo · ${camera.name}` : "En vivo"}
      subtitle="Streaming MJPEG en tiempo real desde tu Raspberry Pi"
      action={
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => navigate("/cameras")}
            className="bg-white/5 border-white/15 text-white hover:bg-white/10"
            data-testid="back-to-cameras-button"
          >
            <ArrowLeft className="w-4 h-4 mr-1.5" /> Volver
          </Button>
          <Button
            onClick={goFullscreen}
            className="bg-blue-600 hover:bg-blue-700"
            data-testid="fullscreen-button"
          >
            <Maximize2 className="w-4 h-4 mr-1.5" /> Pantalla completa
          </Button>
        </div>
      }
    >
      {error ? (
        <div className="rounded-xl bg-[#12141D] border border-red-500/20 p-8 text-center">
          <AlertTriangle className="w-10 h-10 mx-auto text-red-400 mb-3" />
          <div className="text-red-400">{error}</div>
        </div>
      ) : !streamUrl ? (
        <div className="aspect-video bg-black rounded-xl border border-white/10 flex items-center justify-center text-gray-500">
          Cargando...
        </div>
      ) : (
        <div className="space-y-4">
          <div className="relative aspect-video bg-black rounded-xl border border-white/10 overflow-hidden">
            {/* Browser displays multipart/x-mixed-replace natively */}
            <img
              id="live-stream-img"
              src={streamUrl}
              alt="Live stream"
              className="w-full h-full object-contain"
              data-testid="live-stream-img"
              onError={() => setError("No se pudo cargar el stream. El agente debe estar enviando frames.")}
            />
            <div className="absolute top-4 left-4 flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-black/70 border border-white/10 text-xs font-mono uppercase tracking-widest text-red-400 backdrop-blur-md">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 live-dot" />
              LIVE
            </div>
            <div className="absolute bottom-4 left-4 px-2.5 py-1.5 rounded-md bg-black/70 border border-white/10 text-xs font-mono backdrop-blur-md">
              {camera?.name}
            </div>
            <div className="absolute bottom-4 right-4 px-2.5 py-1.5 rounded-md bg-black/70 border border-white/10 text-[10px] font-mono uppercase tracking-widest text-gray-400 backdrop-blur-md flex items-center gap-1.5">
              <Radio className="w-3 h-3 text-blue-400" /> MJPEG · ~5fps
            </div>
          </div>

          <div className="rounded-xl bg-[#12141D] border border-white/10 p-5 text-sm text-gray-400 space-y-2">
            <div className="text-[10px] uppercase tracking-widest font-mono text-gray-500">Cómo funciona</div>
            <p>
              Tu agente Raspberry envía frames JPEG a ~5fps al backend. El navegador los renderiza nativamente como stream MJPEG.
              La latencia típica es de <span className="text-blue-300">0.5–1.5s</span> dependiendo de tu red.
            </p>
            <p className="text-xs text-gray-500">
              Si quieres más fps o calidad, ajusta en la Pi:
              <code className="ml-1 px-1.5 py-0.5 bg-white/5 rounded text-blue-300 font-mono">SMARTCAM_STREAM_FPS=10</code>{" "}
              <code className="ml-1 px-1.5 py-0.5 bg-white/5 rounded text-blue-300 font-mono">SMARTCAM_STREAM_MAX_WIDTH=960</code>
            </p>
          </div>
        </div>
      )}
    </AppShell>
  );
}
