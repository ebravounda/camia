import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Check, Cctv, ArrowRight, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function Pricing() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [subscribingId, setSubscribingId] = useState(null);

  useEffect(() => {
    (async () => {
      try { const { data } = await api.get("/plans"); setPlans(data || []); }
      finally { setLoading(false); }
    })();
  }, []);

  const subscribe = async (planId) => {
    if (!user) { navigate("/login"); return; }
    if (planId === "free") { toast.info("Ya tienes acceso al plan Free"); return; }
    setSubscribingId(planId);
    try {
      const { data } = await api.post("/billing/checkout", {
        plan_id: planId,
        origin_url: window.location.origin,
      });
      if (data?.url) window.location.href = data.url;
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setSubscribingId(null);
    }
  };

  const currentPlan = user?.subscription_plan || "free";

  return (
    <div className="min-h-screen bg-[#090A0F] text-white" data-testid="pricing-page">
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#090A0F]/75 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 sm:px-8 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
              <Cctv className="w-5 h-5 text-white" />
            </div>
            <div className="font-display text-base font-bold tracking-tight">SmartCam SaaS</div>
          </Link>
          <div className="flex items-center gap-2">
            {user ? (
              <Link to="/dashboard"><Button variant="outline" className="bg-white/5 border-white/15 text-white hover:bg-white/10">Ir al panel</Button></Link>
            ) : (
              <>
                <Link to="/login"><Button variant="ghost" className="text-gray-300">Entrar</Button></Link>
                <Link to="/register"><Button className="bg-blue-600 hover:bg-blue-700">Crear cuenta</Button></Link>
              </>
            )}
          </div>
        </div>
      </header>

      <section className="max-w-6xl mx-auto px-6 sm:px-8 py-20">
        <div className="text-center max-w-2xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5 text-xs font-mono uppercase tracking-widest text-blue-400 mb-5">
            <Sparkles className="w-3 h-3" /> Planes simples
          </div>
          <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight">
            Empieza gratis. Escala cuando lo necesites.
          </h1>
          <p className="mt-4 text-gray-400">Suscripción mensual via Stripe. Sin permanencia. Cancela cuando quieras.</p>
        </div>

        {loading ? (
          <div className="mt-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-blue-500" /></div>
        ) : (
          <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-5">
            {plans.map((p) => {
              const isCurrent = currentPlan === p.id && user?.subscription_status === "active";
              const isPro = p.id === "pro";
              return (
                <div
                  key={p.id}
                  data-testid={`pricing-card-${p.id}`}
                  className={`relative rounded-2xl border p-7 flex flex-col ${
                    isPro
                      ? "border-blue-500/40 bg-gradient-to-b from-blue-500/[0.07] to-[#12141D] shadow-[0_0_30px_rgba(59,130,246,0.15)]"
                      : "border-white/10 bg-[#12141D]"
                  }`}
                >
                  {isPro && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-blue-600 text-white text-[10px] uppercase tracking-widest font-mono">
                      Más popular
                    </div>
                  )}
                  <div className="font-display text-xl font-semibold">{p.name}</div>
                  <div className="mt-3 flex items-baseline gap-1">
                    <span className="font-display text-5xl font-bold tracking-tight">${p.price_monthly}</span>
                    <span className="text-sm text-gray-500">/ mes</span>
                  </div>

                  <ul className="mt-6 space-y-2.5 flex-1">
                    {p.features.map((f) => (
                      <li key={f} className="flex items-start gap-2.5 text-sm text-gray-300">
                        <Check className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>

                  <Button
                    data-testid={`subscribe-${p.id}-button`}
                    disabled={isCurrent || subscribingId === p.id}
                    onClick={() => subscribe(p.id)}
                    className={`mt-7 h-11 ${
                      isPro
                        ? "bg-blue-600 hover:bg-blue-700 shadow-[0_0_14px_rgba(37,99,235,0.35)]"
                        : "bg-white/10 hover:bg-white/15 border border-white/10"
                    } text-white`}
                  >
                    {isCurrent ? "Plan actual" :
                      subscribingId === p.id ? <Loader2 className="w-4 h-4 animate-spin" /> :
                      p.price_monthly === 0 ? "Empezar gratis" : (
                        <>Suscribirse <ArrowRight className="w-4 h-4 ml-1.5" /></>
                      )}
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
