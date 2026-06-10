import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, Radio, Maximize2, AlertTriangle, Camera as CameraIcon,
  Pause, Play, Activity, Cpu, RefreshCcw, Volume2, VolumeX,
} from "lucide-react";
import api from "@/lib/api";
import { toast } from "sonner";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const AUDIO_SAMPLE_RATE = 16000;
const VIDEO_MARKER = 0x01;
const AUDIO_MARKER = 0x02;

export default function CameraLive() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [camera, setCamera] = useState(null);
  const [error, setError] = useState("");
  const [playing, setPlaying] = useState(true);
  const [muted, setMuted] = useState(true);  // start muted (browser autoplay policy)
  const [hasAudio, setHasAudio] = useState(false);
  const [fps, setFps] = useState(0);
  const [frameCount, setFrameCount] = useState(0);
  const [streamRes, setStreamRes] = useState({ w: 0, h: 0 });

  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const wsRef = useRef(null);
  const fpsTickRef = useRef({ count: 0, lastTs: Date.now() });
  // Audio playback
  const audioCtxRef = useRef(null);
  const audioGainRef = useRef(null);
  const nextAudioPlayTimeRef = useRef(0);
  const mutedRef = useRef(muted);
  useEffect(() => { mutedRef.current = muted; }, [muted]);

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

  // WebSocket multiplexed stream (video JPEG + audio PCM)
  useEffect(() => {
    if (!playing) {
      if (wsRef.current) { try { wsRef.current.close(); } catch {} wsRef.current = null; }
      return;
    }
    const token = localStorage.getItem("sc_access_token") || "";
    const wsScheme = BACKEND.startsWith("https") ? "wss" : "ws";
    const wsHost = BACKEND.replace(/^https?:\/\//, "");
    const url = `${wsScheme}://${wsHost}/api/ws/cameras/${id}/stream?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");

    const handleVideo = async (buf) => {
      try {
        const blob = new Blob([buf], { type: "image/jpeg" });
        const bitmap = await createImageBitmap(blob);
        if (canvas && ctx) {
          if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
            canvas.width = bitmap.width;
            canvas.height = bitmap.height;
            setStreamRes({ w: bitmap.width, h: bitmap.height });
          }
          ctx.drawImage(bitmap, 0, 0);
          bitmap.close?.();
        }
        fpsTickRef.current.count += 1;
        setFrameCount((c) => c + 1);
      } catch {}
    };

    const handleAudio = (buf) => {
      setHasAudio(true);
      if (mutedRef.current) {
        // Skip decoding when muted — saves CPU and avoids autoplay errors
        return;
      }
      let ctx2 = audioCtxRef.current;
      if (!ctx2) {
        try {
          ctx2 = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: AUDIO_SAMPLE_RATE });
          const gain = ctx2.createGain();
          gain.gain.value = 1.0;
          gain.connect(ctx2.destination);
          audioGainRef.current = gain;
          audioCtxRef.current = ctx2;
          nextAudioPlayTimeRef.current = ctx2.currentTime + 0.15;  // ~150ms jitter buffer
        } catch (e) { console.warn("AudioContext failed:", e); return; }
      }
      if (ctx2.state === "suspended") {
        ctx2.resume().catch(() => {});
      }
      try {
        // Convert s16le PCM to Float32 [-1, 1]
        const pcm = new Int16Array(buf);
        if (pcm.length === 0) return;
        const f32 = new Float32Array(pcm.length);
        for (let i = 0; i < pcm.length; i++) f32[i] = pcm[i] / 32768;
        const abuf = ctx2.createBuffer(1, f32.length, AUDIO_SAMPLE_RATE);
        abuf.getChannelData(0).set(f32);
        const src = ctx2.createBufferSource();
        src.buffer = abuf;
        src.connect(audioGainRef.current);
        const now = ctx2.currentTime;
        let when = nextAudioPlayTimeRef.current;
        if (when < now + 0.02) when = now + 0.02;  // re-anchor if we drifted
        if (when > now + 0.5) when = now + 0.15;   // cap forward drift (skip backlog)
        src.start(when);
        nextAudioPlayTimeRef.current = when + abuf.duration;
      } catch (e) {
        // swallow audio errors silently — keep video flowing
      }
    };

    ws.onmessage = (evt) => {
      if (typeof evt.data === "string") return;
      const buf = evt.data;
      if (!(buf instanceof ArrayBuffer) || buf.byteLength < 1) return;
      const marker = new Uint8Array(buf, 0, 1)[0];
      const payload = buf.slice(1);
      if (marker === VIDEO_MARKER) handleVideo(payload);
      else if (marker === AUDIO_MARKER) handleAudio(payload);
    };

    ws.onclose = () => {
      wsRef.current = null;
      if (playing) {
        setTimeout(() => { if (playing && !wsRef.current) reload(); }, 2000);
      }
    };

    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        try { ws.send("ping"); } catch {}
      }
    }, 15000);

    return () => {
      clearInterval(ping);
      try { ws.close(); } catch {}
      wsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, playing]);

  // FPS estimator
  useEffect(() => {
    if (!playing) { setFps(0); return; }
    const iv = setInterval(() => {
      const now = Date.now();
      const elapsed = (now - fpsTickRef.current.lastTs) / 1000;
      if (elapsed >= 1) {
        setFps(Math.round((fpsTickRef.current.count / elapsed) * 10) / 10);
        fpsTickRef.current.count = 0;
        fpsTickRef.current.lastTs = now;
      }
    }, 1000);
    return () => clearInterval(iv);
  }, [playing]);

  // Tear down audio context on unmount
  useEffect(() => () => {
    try { audioCtxRef.current?.close(); } catch {}
    audioCtxRef.current = null;
  }, []);

  const toggleMute = async () => {
    const next = !muted;
    setMuted(next);
    // Unmute requires a user gesture to start AudioContext
    if (!next && !audioCtxRef.current) {
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: AUDIO_SAMPLE_RATE });
        const gain = ctx.createGain();
        gain.gain.value = 1.0;
        gain.connect(ctx.destination);
        await ctx.resume();
        audioGainRef.current = gain;
        audioCtxRef.current = ctx;
        nextAudioPlayTimeRef.current = ctx.currentTime + 0.15;
      } catch (e) {
        toast.error("Tu navegador bloqueó el audio");
        setMuted(true);
        return;
      }
    }
    if (next && audioCtxRef.current) {
      try { audioCtxRef.current.suspend(); } catch {}
    } else if (!next && audioCtxRef.current?.state === "suspended") {
      try { await audioCtxRef.current.resume(); } catch {}
    }
  };

  const goFullscreen = () => {
    const el = containerRef.current;
    if (el?.requestFullscreen) el.requestFullscreen();
  };

  const takeSnapshot = async () => {
    try {
      const canvas = canvasRef.current;
      if (!canvas) throw new Error("no canvas");
      const blob = await new Promise((r) => canvas.toBlob(r, "image/jpeg", 0.95));
      if (!blob) throw new Error("encode failed");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      a.download = `${camera?.name || "smartcam"}-${stamp}.jpg`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Captura guardada");
    } catch {
      toast.error("No se pudo capturar");
    }
  };

  const reload = () => {
    setFrameCount(0);
    fpsTickRef.current = { count: 0, lastTs: Date.now() };
    if (wsRef.current) { try { wsRef.current.close(); } catch {} }
    setPlaying(false);
    setTimeout(() => setPlaying(true), 100);
  };

  const resTag = streamRes.h >= 1000 ? "FHD" : streamRes.h >= 700 ? "HD" : streamRes.h > 0 ? "SD" : (camera?.resolution || "—");

  return (
    <AppShell
      title={camera ? `En vivo · ${camera.name}` : "En vivo"}
      subtitle={`Streaming WebSocket · ${resTag}${hasAudio ? " · audio" : ""}`}
      action={
        <Button
          variant="outline"
          onClick={() => navigate("/cameras")}
          className="bg-white/5 border-white/15 text-white hover:bg-white/10 rounded-none"
          data-testid="back-to-cameras-button"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" /> Cámaras
        </Button>
      }
    >
      {error ? (
        <div className="bg-[#0F0F0F] border border-red-500/20 p-8 text-center">
          <AlertTriangle className="w-10 h-10 mx-auto text-red-400 mb-3" />
          <div className="text-red-400">{error}</div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Cinema-style player */}
          <div
            ref={containerRef}
            className="relative aspect-video bg-black border border-white/10 overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.6)]"
            data-testid="player-container"
          >
            {playing ? (
              <canvas
                ref={canvasRef}
                className="absolute inset-0 w-full h-full object-contain"
                data-testid="live-stream-canvas"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-gray-500 text-sm">
                <Pause className="w-10 h-10 opacity-50" />
              </div>
            )}

            {/* Top HUD bar */}
            <div className="absolute top-0 left-0 right-0 px-2 sm:px-4 py-2 sm:py-3 flex items-center justify-between bg-gradient-to-b from-black/70 to-transparent pointer-events-none">
              <div className="flex items-center gap-1.5 px-2 py-1 bg-black/60 border border-white/10 text-[10px] sm:text-[11px] font-mono uppercase tracking-widest text-[#C8FF00] backdrop-blur-md">
                <span className={`w-1.5 h-1.5 ${playing ? "bg-[#C8FF00] live-dot animate-pulse" : "bg-gray-500"}`} />
                {playing ? "LIVE" : "PAUSADO"}
              </div>
              <div className="flex items-center gap-1.5 px-2 py-1 bg-black/60 border border-white/10 text-[10px] font-mono uppercase tracking-widest text-gray-300 backdrop-blur-md">
                <Activity className="w-3 h-3 text-[#C8FF00]" />
                <span className="hidden sm:inline">{fps.toFixed(1)} fps · {streamRes.w}×{streamRes.h} · {frameCount}</span>
                <span className="sm:hidden">{fps.toFixed(0)} fps · {resTag}</span>
              </div>
            </div>

            {/* Bottom HUD bar */}
            <div className="absolute bottom-0 left-0 right-0 px-2 sm:px-4 py-2 sm:py-3 flex items-center justify-between bg-gradient-to-t from-black/70 to-transparent">
              <div className="px-2 py-1 bg-black/60 border border-white/10 text-[10px] sm:text-[11px] font-mono backdrop-blur-md truncate max-w-[40%]">
                {camera?.name || "—"}
              </div>
              <div className="flex items-center gap-1 sm:gap-1.5 pointer-events-auto">
                <button
                  onClick={toggleMute}
                  disabled={!hasAudio}
                  className={`w-11 h-11 sm:w-9 sm:h-9 backdrop-blur-md border flex items-center justify-center transition-all hover:scale-105 ${
                    !hasAudio ? "bg-white/5 border-white/10 text-gray-600 cursor-not-allowed"
                      : muted ? "bg-white/10 border-white/15 text-white hover:bg-white/20"
                      : "bg-[#C8FF00] border-[#C8FF00] text-black hover:bg-[#D8FF20]"
                  }`}
                  title={!hasAudio ? "Sin audio disponible" : (muted ? "Activar audio" : "Silenciar")}
                  data-testid="player-mute"
                >
                  {muted ? <VolumeX className="w-5 h-5 sm:w-4 sm:h-4" /> : <Volume2 className="w-5 h-5 sm:w-4 sm:h-4" />}
                </button>
                <button
                  onClick={() => setPlaying((p) => !p)}
                  className="w-11 h-11 sm:w-9 sm:h-9 bg-white/10 active:bg-white/30 hover:bg-white/20 backdrop-blur-md border border-white/15 flex items-center justify-center transition-all hover:scale-105"
                  title={playing ? "Pausar" : "Reanudar"}
                  data-testid="player-play-pause"
                >
                  {playing ? <Pause className="w-5 h-5 sm:w-4 sm:h-4 text-white" /> : <Play className="w-5 h-5 sm:w-4 sm:h-4 text-white" />}
                </button>
                <button
                  onClick={reload}
                  className="w-11 h-11 sm:w-9 sm:h-9 bg-white/10 active:bg-white/30 hover:bg-white/20 backdrop-blur-md border border-white/15 flex items-center justify-center transition-all hover:scale-105"
                  title="Reconectar"
                  data-testid="player-reload"
                >
                  <RefreshCcw className="w-5 h-5 sm:w-4 sm:h-4 text-white" />
                </button>
                <button
                  onClick={takeSnapshot}
                  className="w-11 h-11 sm:w-9 sm:h-9 bg-white/10 active:bg-white/30 hover:bg-white/20 backdrop-blur-md border border-white/15 flex items-center justify-center transition-all hover:scale-105"
                  title="Capturar foto"
                  data-testid="player-snapshot"
                >
                  <CameraIcon className="w-5 h-5 sm:w-4 sm:h-4 text-white" />
                </button>
                <button
                  onClick={goFullscreen}
                  className="w-11 h-11 sm:w-9 sm:h-9 bg-[#C8FF00] active:bg-[#A8DF00] hover:bg-[#D8FF20] border border-[#C8FF00] flex items-center justify-center transition-all hover:scale-105 shadow-[0_0_14px_rgba(200,255,0,0.45)]"
                  title="Pantalla completa"
                  data-testid="player-fullscreen"
                >
                  <Maximize2 className="w-5 h-5 sm:w-4 sm:h-4 text-black" />
                </button>
              </div>
            </div>
          </div>

          {/* Info bar */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-[#0F0F0F] border border-white/10 p-4 flex items-center gap-3 hover:border-[#C8FF00] transition-colors">
              <div className="w-10 h-10 bg-[#C8FF00]/10 border border-[#C8FF00]/20 flex items-center justify-center">
                <Radio className="w-5 h-5 text-[#C8FF00]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[10px] uppercase tracking-widest font-mono text-gray-500">Resolución</div>
                <div className="text-sm">{streamRes.w}×{streamRes.h || "—"} · {resTag}</div>
              </div>
            </div>
            <div className="bg-[#0F0F0F] border border-white/10 p-4 flex items-center gap-3 hover:border-[#C8FF00] transition-colors">
              <div className="w-10 h-10 bg-[#C8FF00]/10 border border-[#C8FF00]/20 flex items-center justify-center">
                <Activity className="w-5 h-5 text-[#C8FF00]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[10px] uppercase tracking-widest font-mono text-gray-500">Fluidez</div>
                <div className="text-sm">{fps.toFixed(1)} fps actuales</div>
              </div>
            </div>
            <div className="bg-[#0F0F0F] border border-white/10 p-4 flex items-center gap-3 hover:border-[#C8FF00] transition-colors">
              <div className="w-10 h-10 bg-[#C8FF00]/10 border border-[#C8FF00]/20 flex items-center justify-center">
                {hasAudio
                  ? (muted ? <VolumeX className="w-5 h-5 text-[#C8FF00]" /> : <Volume2 className="w-5 h-5 text-[#C8FF00]" />)
                  : <Cpu className="w-5 h-5 text-[#C8FF00]" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[10px] uppercase tracking-widest font-mono text-gray-500">Audio</div>
                <div className="text-sm">{hasAudio ? (muted ? "Disponible · silenciado" : "Reproduciendo · 16 kHz mono") : "No detectado en el Pi"}</div>
              </div>
            </div>
          </div>

          <div className="bg-[#0F0F0F] border border-white/10 p-4 text-xs text-gray-400">
            <span className="text-gray-500 font-mono uppercase tracking-widest text-[10px]">Tip</span>
            <span className="ml-2">
              Cambia la calidad <strong className="text-[#C8FF00]">HD/FHD</strong> desde la página <a href="/cameras" className="text-[#C8FF00] underline">Cámaras</a>.
              Si tu Pi tiene micrófono conectado, el audio se detecta automáticamente.
            </span>
          </div>
        </div>
      )}
    </AppShell>
  );
}
