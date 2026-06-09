import Sidebar from "@/components/Sidebar";

export default function AppShell({ children, title, subtitle, action }) {
  return (
    <div className="min-h-screen flex bg-[#090A0F] text-white">
      <Sidebar />
      <main className="flex-1 min-w-0">
        <header className="sticky top-0 z-30 backdrop-blur-xl bg-[#090A0F]/75 border-b border-white/10">
          <div className="px-6 sm:px-8 py-5 flex items-center justify-between gap-4">
            <div>
              <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight" data-testid="page-title">
                {title}
              </h1>
              {subtitle && (
                <p className="text-sm text-gray-400 mt-1">{subtitle}</p>
              )}
            </div>
            {action}
          </div>
        </header>
        <div className="p-6 sm:p-8 lg:p-10">{children}</div>
      </main>
    </div>
  );
}
