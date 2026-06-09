import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { CheckCircle2, Loader2, XCircle, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function BillingSuccess() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [status, setStatus] = useState("polling"); // polling | paid | failed
  const [planId, setPlanId] = useState(null);
  const attempts = useRef(0);

  useEffect(() => {
    if (!sessionId) { setStatus("failed"); return; }
    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      attempts.current += 1;
      try {
        const { data } = await api.get(`/billing/status/${sessionId}`);
        if (data.payment_status === "paid") {
          setStatus("paid");
          setPlanId(data.plan_id);
          await refresh();
          return;
        }
        if (data.status === "expired" || attempts.current > 10) {
          setStatus("failed");
          return;
        }
      } catch {
        // ignore and retry
      }
      setTimeout(poll, 2000);
    };
    poll();
    return () => { cancelled = true; };
  }, [sessionId, refresh]);

  return (
    <div className="min-h-screen bg-[#090A0F] text-white flex items-center justify-center px-4" data-testid="billing-success-page">
      <div className="max-w-md w-full bg-[#12141D] border border-white/10 rounded-2xl p-8 text-center">
        {status === "polling" && (
          <>
            <Loader2 className="w-12 h-12 mx-auto text-blue-500 animate-spin" />
            <h1 className="font-display text-2xl font-semibold mt-5">Procesando pago...</h1>
            <p className="text-sm text-gray-400 mt-2">Esto solo tardará unos segundos.</p>
          </>
        )}
        {status === "paid" && (
          <>
            <CheckCircle2 className="w-14 h-14 mx-auto text-emerald-400" />
            <h1 className="font-display text-2xl font-semibold mt-5" data-testid="billing-success-title">¡Pago exitoso!</h1>
            <p className="text-sm text-gray-400 mt-2">
              Tu plan <span className="text-blue-300 font-medium capitalize">{planId}</span> está activo.
            </p>
            <Button
              data-testid="billing-success-cta"
              className="w-full mt-6 bg-blue-600 hover:bg-blue-700"
              onClick={() => navigate("/dashboard")}
            >
              Ir al dashboard <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
          </>
        )}
        {status === "failed" && (
          <>
            <XCircle className="w-14 h-14 mx-auto text-red-400" />
            <h1 className="font-display text-2xl font-semibold mt-5">No se pudo confirmar el pago</h1>
            <p className="text-sm text-gray-400 mt-2">Si el cargo fue realizado, se reflejará en unos minutos.</p>
            <Link to="/pricing">
              <Button variant="outline" className="w-full mt-6 bg-white/5 border-white/15 text-white hover:bg-white/10">
                Volver a planes
              </Button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
