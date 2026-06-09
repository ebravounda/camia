import AppShell from "@/components/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "react-router-dom";
import { Cloud, MessageCircle, User, CreditCard, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function Settings() {
  const { user } = useAuth();

  const Section = ({ icon: Icon, title, desc, children, testid }) => (
    <div data-testid={testid} className="rounded-xl bg-[#12141D] border border-white/10 p-6">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
          <Icon className="w-5 h-5 text-blue-400" />
        </div>
        <div>
          <div className="font-display text-base font-semibold">{title}</div>
          <div className="text-xs text-gray-500 mt-0.5">{desc}</div>
        </div>
      </div>
      {children}
    </div>
  );

  return (
    <AppShell title="Configuración" subtitle="Cuenta, suscripción e integraciones">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Section icon={User} title="Cuenta" desc="Tus datos personales" testid="settings-account">
          <div className="space-y-3">
            <div>
              <Label className="text-xs uppercase tracking-widest font-mono text-gray-400">Nombre</Label>
              <Input value={user?.name || ""} disabled className="bg-[#090A0F] border-white/10 mt-1.5" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-widest font-mono text-gray-400">Email</Label>
              <Input value={user?.email || ""} disabled className="bg-[#090A0F] border-white/10 mt-1.5" />
            </div>
            <div className="text-xs text-gray-500">
              Auth: <span className="font-mono text-blue-300">{user?.auth_provider}</span>
            </div>
          </div>
        </Section>

        <Section icon={CreditCard} title="Suscripción" desc="Gestiona tu plan" testid="settings-subscription">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm text-gray-400">Plan actual</div>
              <div className="font-display text-xl font-semibold capitalize mt-1">{user?.subscription_plan}</div>
            </div>
            <Badge className={user?.subscription_status === "active"
              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
              : "bg-white/5 text-gray-400 border border-white/10"}>
              {user?.subscription_status}
            </Badge>
          </div>
          <Link to="/pricing" data-testid="settings-upgrade-link">
            <Button className="w-full bg-blue-600 hover:bg-blue-700">
              {user?.subscription_status === "active" ? "Cambiar plan" : "Mejorar plan"}
            </Button>
          </Link>
        </Section>

        <Section icon={Cloud} title="Google Drive" desc="Almacenamiento de clips y grabaciones" testid="settings-gdrive">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-400">
              {user?.google_drive_connected ? "Conectado" : "No conectado"}
            </div>
            <Button variant="outline" className="bg-white/5 border-white/15 text-white hover:bg-white/10" disabled data-testid="settings-gdrive-connect">
              Conectar <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
            </Button>
          </div>
          <div className="text-[11px] text-gray-500 font-mono mt-3 uppercase tracking-widest">Disponible en Fase 4</div>
        </Section>

        <Section icon={MessageCircle} title="Alertas WhatsApp" desc="Notificaciones vía Twilio" testid="settings-whatsapp">
          <div className="space-y-3">
            <Label className="text-xs uppercase tracking-widest font-mono text-gray-400">Número WhatsApp</Label>
            <Input placeholder="+34 600 000 000" defaultValue={user?.whatsapp_number || ""} disabled className="bg-[#090A0F] border-white/10" />
            <div className="text-[11px] text-gray-500 font-mono uppercase tracking-widest">Disponible en Fase 6</div>
          </div>
        </Section>
      </div>
    </AppShell>
  );
}
