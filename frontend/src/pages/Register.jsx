import { useState } from "react";
import { Link, useNavigate, Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { formatApiError } from "@/lib/api";
import { Cctv, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function Register() {
  const { user, register, loading } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!loading && user) return <Navigate to="/dashboard" replace />;

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await register(name, email, password);
      toast.success("Cuenta creada. ¡Bienvenido!");
      navigate("/dashboard");
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  const onGoogle = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#090A0F] text-white px-4" data-testid="register-page">
      <div className="absolute inset-0 opacity-25 pointer-events-none"
           style={{ backgroundImage: "radial-gradient(circle at 50% 0%, rgba(59,130,246,0.15), transparent 60%)" }} />
      <div className="relative w-full max-w-md">
        <Link to="/" className="flex items-center gap-2.5 mb-8 justify-center">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-[0_0_14px_rgba(59,130,246,0.45)]">
            <Cctv className="w-5 h-5 text-white" />
          </div>
          <div className="font-display text-lg font-bold tracking-tight">SmartCam SaaS</div>
        </Link>

        <div className="bg-[#12141D] border border-white/10 rounded-2xl p-8 shadow-2xl">
          <h1 className="font-display text-2xl font-semibold tracking-tight">Crear cuenta</h1>
          <p className="text-sm text-gray-400 mt-1">Empieza gratis. Sin tarjeta.</p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name" className="text-xs uppercase tracking-widest text-gray-400 font-mono">Nombre</Label>
              <Input id="name" data-testid="register-name-input" required value={name} onChange={(e) => setName(e.target.value)}
                placeholder="Tu nombre" className="bg-[#090A0F] border-white/10 focus-visible:ring-blue-500 h-11" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email" className="text-xs uppercase tracking-widest text-gray-400 font-mono">Email</Label>
              <Input id="email" type="email" data-testid="register-email-input" required value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="tucorreo@empresa.com" className="bg-[#090A0F] border-white/10 focus-visible:ring-blue-500 h-11" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-xs uppercase tracking-widest text-gray-400 font-mono">Contraseña</Label>
              <Input id="password" type="password" data-testid="register-password-input" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="Mínimo 6 caracteres" className="bg-[#090A0F] border-white/10 focus-visible:ring-blue-500 h-11" />
            </div>

            {error && (
              <div data-testid="register-error" className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-3 py-2">
                {error}
              </div>
            )}

            <Button
              type="submit"
              data-testid="register-submit-button"
              disabled={submitting}
              className="w-full h-11 bg-blue-600 hover:bg-blue-700 text-white shadow-[0_0_14px_rgba(37,99,235,0.35)]"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Crear cuenta"}
            </Button>
          </form>

          <div className="my-6 flex items-center gap-3">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-[10px] uppercase tracking-[0.2em] text-gray-500 font-mono">o</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          <Button
            type="button"
            onClick={onGoogle}
            data-testid="register-google-button"
            variant="outline"
            className="w-full h-11 bg-white/5 hover:bg-white/10 border-white/15 text-white"
          >
            <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"/>
            </svg>
            Continuar con Google
          </Button>

          <p className="mt-6 text-sm text-gray-400 text-center">
            ¿Ya tienes cuenta?{" "}
            <Link to="/login" className="text-blue-400 hover:text-blue-300 font-medium" data-testid="register-login-link">
              Inicia sesión
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
