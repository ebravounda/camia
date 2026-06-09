import { Link } from "react-router-dom";
import { Cctv, Shield, Zap, MessageCircle, Cloud, Cpu, ArrowRight, Check } from "lucide-react";
import { Button } from "@/components/ui/button";

const features = [
  {
    icon: Cpu,
    title: "IA en el borde",
    desc: "YOLOv8n y reconocimiento facial corriendo directamente en tu Raspberry Pi. Sin latencia, sin compromisos.",
  },
  {
    icon: Cctv,
    title: "Hasta 4 cámaras USB",
    desc: "Conecta hasta 4 cámaras por dispositivo. Stream en tiempo real al panel web con grid 2x2.",
  },
  {
    icon: Cloud,
    title: "Google Drive 7 días",
    desc: "Grabación continua y clips de eventos subidos automáticamente a tu Google Drive. Rotación automática.",
  },
  {
    icon: MessageCircle,
    title: "Alertas WhatsApp",
    desc: "Notificación instantánea por WhatsApp con miniatura y link al clip cuando se detecta un evento sospechoso.",
  },
  {
    icon: Shield,
    title: "Privacidad primero",
    desc: "El video se procesa localmente. Solo metadatos y eventos clave llegan a la nube. Tú controlas qué se sube.",
  },
  {
    icon: Zap,
    title: "Detección inteligente",
    desc: "Merodeo, persona desconocida en horario nocturno, intento de forzar puerta. Más allá del simple movimiento.",
  },
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#090A0F] text-white" data-testid="landing-page">
      {/* Nav */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#090A0F]/75 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 sm:px-8 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5" data-testid="landing-logo">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-[0_0_14px_rgba(59,130,246,0.45)]">
              <Cctv className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-display text-base font-bold tracking-tight">SmartCam</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500 font-mono">SaaS</div>
            </div>
          </Link>
          <div className="flex items-center gap-2">
            <Link to="/pricing" className="hidden sm:inline-block text-sm text-gray-400 hover:text-white px-3 py-2" data-testid="landing-pricing-link">
              Planes
            </Link>
            <Link to="/login" className="text-sm text-gray-300 hover:text-white px-3 py-2" data-testid="landing-login-link">
              Entrar
            </Link>
            <Link to="/register" data-testid="landing-register-cta">
              <Button className="bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-[0_0_15px_rgba(37,99,235,0.35)]">
                Empezar gratis
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-white/10">
        <div
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              "url(https://images.unsplash.com/photo-1714548529197-537c1f0b6aa7?w=1920&q=80)",
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-[#090A0F]/40 via-[#090A0F]/85 to-[#090A0F]" />
        <div className="relative max-w-6xl mx-auto px-6 sm:px-8 pt-24 pb-32 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5 text-xs font-mono uppercase tracking-widest text-blue-400 mb-6">
            <span className="w-1.5 h-1.5 bg-blue-400 rounded-full live-dot" />
            Videovigilancia con IA · Raspberry Pi
          </div>
          <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.05]">
            Convierte tu Raspberry Pi en un<br />
            <span className="bg-gradient-to-r from-blue-400 via-blue-500 to-cyan-400 bg-clip-text text-transparent">
              guardián de seguridad
            </span> inteligente.
          </h1>
          <p className="mt-6 text-lg sm:text-xl text-gray-400 max-w-2xl mx-auto leading-relaxed">
            Conecta hasta 4 cámaras USB, detecta personas, caras y comportamientos sospechosos
            con IA local, y recibe alertas en WhatsApp. Todo en una plataforma SaaS.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link to="/register" data-testid="hero-register-cta">
              <Button size="lg" className="bg-blue-600 hover:bg-blue-700 text-white font-medium h-12 px-6 shadow-[0_0_22px_rgba(37,99,235,0.45)] hover:shadow-[0_0_30px_rgba(37,99,235,0.6)] transition-all">
                Crear cuenta gratis
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/pricing" data-testid="hero-pricing-cta">
              <Button size="lg" variant="outline" className="bg-white/5 hover:bg-white/10 text-white border-white/15 h-12 px-6">
                Ver planes
              </Button>
            </Link>
          </div>
          <div className="mt-12 flex flex-wrap items-center justify-center gap-x-8 gap-y-2 text-xs text-gray-500 font-mono uppercase tracking-widest">
            <span className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-blue-400" /> Sin tarjeta</span>
            <span className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-blue-400" /> Setup en 10 min</span>
            <span className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-blue-400" /> Datos en tu Drive</span>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-7xl mx-auto px-6 sm:px-8 py-24">
        <div className="max-w-2xl">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-blue-400 mb-3">Capacidades</div>
          <h2 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight">
            Todo lo que necesitas para vigilar tu negocio o casa.
          </h2>
          <p className="mt-4 text-gray-400">
            Una arquitectura híbrida: la IA pesada corre en tu Pi, el panel y la orquestación viven en la nube.
          </p>
        </div>
        <div className="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map((f) => (
            <div
              key={f.title}
              className="group relative p-6 rounded-xl bg-[#12141D] border border-white/10 hover:border-blue-500/40 transition-all hover:shadow-[0_0_22px_rgba(59,130,246,0.12)]"
              data-testid={`feature-${f.title.replace(/\s+/g, "-").toLowerCase()}`}
            >
              <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-4 group-hover:bg-blue-500/20 transition-colors">
                <f.icon className="w-5 h-5 text-blue-400" />
              </div>
              <h3 className="font-display text-lg font-semibold mb-2">{f.title}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-white/10">
        <div className="max-w-5xl mx-auto px-6 sm:px-8 py-20 text-center">
          <h2 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight">
            Empieza en menos de 10 minutos.
          </h2>
          <p className="mt-3 text-gray-400 max-w-xl mx-auto">
            Crea tu cuenta, vincula tu Raspberry Pi con un token de emparejamiento y configura tus cámaras desde el panel.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link to="/register" data-testid="cta-register">
              <Button size="lg" className="bg-blue-600 hover:bg-blue-700 text-white h-12 px-7">
                Crear cuenta
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/login" data-testid="cta-login">
              <Button size="lg" variant="outline" className="bg-white/5 hover:bg-white/10 text-white border-white/15 h-12 px-7">
                Ya tengo cuenta
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6 sm:px-8 py-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-500">
          <div className="flex items-center gap-2">
            <Cctv className="w-4 h-4 text-blue-500" />
            <span className="font-mono uppercase tracking-widest">SmartCam SaaS · 2026</span>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/login" className="hover:text-white">Entrar</Link>
            <Link to="/pricing" className="hover:text-white">Planes</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
