import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Menu, Cctv } from "lucide-react";

export default function AppShell({ children, title, subtitle, action }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen flex bg-[#090A0F] text-white">
      {/* Desktop sidebar */}
      <div className="hidden md:flex md:sticky md:top-0 md:h-screen">
        <Sidebar />
      </div>

      <main className="flex-1 min-w-0">
        {/* Sticky header with mobile menu */}
        <header className="sticky top-0 z-30 backdrop-blur-xl bg-[#090A0F]/85 border-b border-white/10">
          <div className="px-4 sm:px-6 lg:px-8 py-4 flex items-center gap-3">
            {/* Mobile menu button + brand */}
            <div className="flex items-center gap-3 md:hidden">
              <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
                <SheetTrigger asChild>
                  <button
                    data-testid="mobile-menu-button"
                    className="w-10 h-10 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors"
                    aria-label="Abrir menú"
                  >
                    <Menu className="w-5 h-5" />
                  </button>
                </SheetTrigger>
                <SheetContent side="left" className="p-0 w-64 bg-[#0E1017] border-white/10">
                  <Sidebar onNavigate={() => setMobileOpen(false)} />
                </SheetContent>
              </Sheet>
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-md bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
                  <Cctv className="w-4 h-4 text-white" />
                </div>
                <span className="font-display text-sm font-bold tracking-tight">SmartCam</span>
              </div>
            </div>

            {/* Title (hidden on mobile to save space; subtitle becomes smaller) */}
            <div className="flex-1 min-w-0 hidden sm:block">
              <h1
                className="font-display text-xl sm:text-2xl lg:text-3xl font-semibold tracking-tight truncate"
                data-testid="page-title"
              >
                {title}
              </h1>
              {subtitle && (
                <p className="text-xs sm:text-sm text-gray-400 mt-0.5 truncate">{subtitle}</p>
              )}
            </div>
            {action && (
              <div className="ml-auto shrink-0 flex items-center gap-1.5 [&_button]:h-9 sm:[&_button]:h-10">
                {action}
              </div>
            )}
          </div>

          {/* Mobile-only sub-row showing title (cleaner) */}
          <div className="sm:hidden px-4 pb-3 -mt-1">
            <h1 className="font-display text-lg font-semibold tracking-tight truncate">
              {title}
            </h1>
            {subtitle && <p className="text-xs text-gray-500 truncate">{subtitle}</p>}
          </div>
        </header>

        <div className="p-4 sm:p-6 lg:p-10">{children}</div>
      </main>
    </div>
  );
}
