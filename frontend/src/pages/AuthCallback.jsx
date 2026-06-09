import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

export default function AuthCallback() {
  const hasProcessed = useRef(false);
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash || "";
    const params = new URLSearchParams(hash.replace(/^#/, ""));
    const sessionId = params.get("session_id");

    if (!sessionId) {
      setError("session_id ausente");
      return;
    }

    (async () => {
      try {
        const { data } = await api.post("/auth/google/session", { session_id: sessionId });
        if (data?.access_token) localStorage.setItem("sc_access_token", data.access_token);
        setUser(data.user);
        toast.success("Sesión Google iniciada");
        // Clean hash and redirect
        window.history.replaceState(null, "", "/dashboard");
        navigate("/dashboard", { replace: true, state: { user: data.user } });
      } catch (e) {
        setError(formatApiError(e));
      }
    })();
  }, [navigate, setUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#090A0F] text-white" data-testid="auth-callback">
      <div className="text-center">
        <Loader2 className="w-7 h-7 text-blue-500 animate-spin mx-auto" />
        <div className="mt-4 text-sm text-gray-400">Procesando sesión...</div>
        {error && (
          <div className="mt-4 text-sm text-red-400">{error}</div>
        )}
      </div>
    </div>
  );
}
