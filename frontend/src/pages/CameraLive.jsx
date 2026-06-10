import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, Radio, Maximize2, AlertTriangle, Camera as CameraIcon,
  Pause, Play, Activity, Cpu, RefreshCcw,
} from "lucide-react";
import api from "@/lib/api";
import { toast } from "sonner";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function CameraLive() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [camera, setCamera] = useState(null);
  const [error, setError] = useState("");
  const [playing, setPlaying] = useState(true);
  const [streamUrl, setStreamUrl] = useState("");
  const [fps, setFps] = useState(0);
  const [frameCount, setFrameCount] = useState(0);
  const imgRef = useRef(null);
  const containerRef = useRef(null);
  const fpsTickRef = useRef({ count: 0, lastTs: Date.now() });

  // Load camera info
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/cameras");
        const cam = data.find((c) => c.id === id);
        if (!cam) { setError("Cámara no encontrada"); return; }
        setCamera(cam);
      } catch (e) { setError("Error cargando cámara"); }
    })();
  }, [id]);

  // Build/refresh stream URL when playing toggles
  useEffect(() => {
    if (!playing) { setStreamUrl(""); return; }
    setStreamUrl(`${BACKEND}/api/cameras/${id}/stream.mjpg?t=${Date.now()}`);
  }, [id, playing]);

  // FPS estimator: count `load` events on the <img> over 1s windows.
  // MJPEG multipart triggers a "load"-like event per frame in Chrome/Firefox.
  useEffect(() => {
    if (!playing) { setFps(0); return; }
    const iv = setInterval(() => {
      const now = Date.now();
      const elapsed = (now - fpsTickRef.current.lastTs) / 1000;
      if (elapsed >= 1) {
        const f = fpsTickRef.current.count / elapsed;
        setFps(Math.round(f * 10) / 10);
        fpsTickRef.current.count = 0;
        fpsTickRef.current.lastTs = now;
      }
    }, 1000);
    return () => clearInterval(iv);
  }, [playing]);

  const handleFrame = () => {
    fpsTickRef.current.count += 1;
    setFrameCount((c) => c + 1);
  };

  const goFullscreen = () => {
    const el = containerRef.current;
    if (el?.requestFullscreen) el.requestFullscreen();
  };

  const takeSnapshot = async () => {
    try {
      const res = await fetch(`${BACKEND}/api/cameras/${id}/snapshot.jpg?t=${Date.now()}`, {
        credentials: "include",
        headers: { Authorization: `Bearer ${localStorage.getItem("sc_access_token") || ""}` },
      });
      if (!res.ok) throw new Error("snapshot");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      a.download = `${camera?.name || "smartcam"}-${stamp}.jpg`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Captura guardada");
    } catch {
      toast.error("No se pudo capturar (¿hay stream activo?)");
    }
  };

  const reload = () => {
    setFrameCount(0);
    fpsTickRef.current = { count: 0, lastTs: Date.now() };
    setStreamUrl(`${BACKEND}/api/cameras/${id}/stream.mjpg?t=${Date.now()}`);
  };

  return (
    <AppShell
      title={camera ? `En vivo · ${camera.name}` : "En vivo"}
      subtitle="Streaming en tiempo real con IA"
      action={
        <Button
          variant="outline"
          onClick={() => navigate("/cameras")}
          className="bg-white/5 border-white/15 text-white hover:bg-white/10"
          data-testid="back-to-cameras-button"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" /> Cámaras
        </Button>
      }
    >
      {error ? (
        <div className="rounded-xl bg-[#12141D] border border-red-500/20 p-8 text-center">
          <AlertTriangle className="w-10 h-10 mx-auto text-red-400 mb-3" />
          <div className="text-red-400">{error}</div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Cinema-style player */}
          <div
            ref={containerRef}
            className="relative aspect-video bg-black rounded-2xl border border-white/10 overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.6)]"
            data-testid="player-container"
          >
            {streamUrl ? (
              <img
                ref={imgRef}
                src={streamUrl}
                onLoad={handleFrame}
                alt="Live stream"
                className="absolute inset-0 w-full h-full object-contain"
                data-testid="live-stream-img"
                onError={() => setError("No se pudo cargar el stream. Verifica que el agente esté enviando frames.")}
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-gray-500 text-sm">
                <Pause className="w-10 h-10 opacity-50" />
              </div>
            )}

            {/* Top HUD bar */}
            <div className="absolute top-0 left-0 right-0 px-4 py-3 flex items-center justify-between bg-gradient-to-b from-black/70 to-transparent pointer-events-none">
              <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-black/60 border border-white/10 text-[11px] font-mono uppercase tracking-widest text-red-400 backdrop-blur-md">
                <span className={`w-1.5 h-1.5 rounded-full ${playing ? "bg-red-500 live-dot" : "bg-gray-500"}`} />
                {playing ? "LIVE" : "PAUSADO"}
              </div>
              <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-black/60 border border-white/10 text-[10px] font-mono uppercase tracking-widest text-gray-300 backdrop-blur-md">
                <Activity className="w-3 h-3 text-blue-400" />
                {fps.toFixed(1)} fps · {frameCount} frames
              </div>
            </div>

            {/* Bottom HUD bar */}
            <div className="absolute bottom-0 left-0 right-0 px-4 py-3 flex items-center justify-between bg-gradient-to-t from-black/70 to-transparent">
              <div className="px-2.5 py-1 rounded-md bg-black/60 border border-white/10 text-[11px] font-mono backdrop-blur-md">
                {camera?.name || "—"}
              </div>
              <div className="flex items-center gap-1.5 pointer-events-auto">
                <button
                  onClick={() => setPlaying((p) => !p)}
                  className="w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/15 flex items-center justify-center transition-colors"
                  title={playing ? "Pausar" : "Reanudar"}
                  data-testid="player-play-pause"
                >
                  {playing ? <Pause className="w-4 h-4 text-white" /> : <Play className="w-4 h-4 text-white" />}
                </button>
                <button
                  onClick={reload}
                  className="w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/15 flex items-center justify-center transition-colors"
                  title="Reconectar"
                  data-testid="player-reload"
                >
                  <RefreshCcw className="w-4 h-4 text-white" />
                </button>
                <button
                  onClick={takeSnapshot}
                  className="w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/15 flex items-center justify-center transition-colors"
                  title="Capturar foto"
                  data-testid="player-snapshot"
                >
                  <CameraIcon className="w-4 h-4 text-white" />
                </button>
                <button
                  onClick={goFullscreen}
                  className="w-9 h-9 rounded-full bg-blue-600 hover:bg-blue-700 border border-blue-500 flex items-center justify-center transition-colors shadow-[0_0_14px_rgba(37,99,235,0.45)]"
                  title="Pantalla completa"
                  data-testid="player-fullscreen"
                >
                  <Maximize2 className="w-4 h-4 text-white" />
                </button>
              </div>
            </div>
          </div>

          {/* Info bar */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="rounded-xl bg-[#12141D] border border-white/10 p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                <Radio className="w-5 h-5 text-blue-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[10px] uppercase tracking-widest font-mono text-gray-500">Protocolo</div>
                <div className="text-sm">MJPEG · HTTP multipart</div>
              </div>
            </div>
            <div className="rounded-xl bg-[#12141D] border border-white/10 p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                <Activity className="w-5 h-5 text-emerald-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[10px] uppercase tracking-widest font-mono text-gray-500">Fluidez</div>
                <div className="text-sm">{fps.toFixed(1)} fps actuales</div>
              </div>
            </div>
            <div className="rounded-xl bg-[#12141D] border border-white/10 p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
                <Cpu className="w-5 h-5 text-purple-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[10px] uppercase tracking-widest font-mono text-gray-500">IA</div>
                <div className="text-sm">YOLO + Haar + Motion</div>
              </div>
            </div>
          </div>

          <div className="rounded-xl bg-[#12141D] border border-white/10 p-4 text-xs text-gray-400">
            <span className="text-gray-500 font-mono uppercase tracking-widest text-[10px]">Tip</span>
            <span className="ml-2">
              Para más fluidez ajusta en la Pi:{" "}
              <code className="px-1.5 py-0.5 bg-white/5 rounded text-blue-300 font-mono">SMARTCAM_STREAM_FPS=20</code>{" "}
              <code className="px-1.5 py-0.5 bg-white/5 rounded text-blue-300 font-mono">SMARTCAM_CAM_FPS=20</code>
            </span>
          </div>
        </div>
      )}
    </AppShell>
  );
}
