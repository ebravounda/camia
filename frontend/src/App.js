import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";

import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";

import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import AuthCallback from "@/pages/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import Cameras from "@/pages/Cameras";
import Devices from "@/pages/Devices";
import Events from "@/pages/Events";
import Pricing from "@/pages/Pricing";
import Settings from "@/pages/Settings";
import AdminPanel from "@/pages/AdminPanel";
import BillingSuccess from "@/pages/BillingSuccess";
import CameraLive from "@/pages/CameraLive";

function AppRouter() {
  // Handle Emergent Google Auth callback synchronously during render
  if (typeof window !== "undefined" && window.location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/pricing" element={<Pricing />} />

      <Route
        path="/dashboard"
        element={<ProtectedRoute><Dashboard /></ProtectedRoute>}
      />
      <Route
        path="/cameras"
        element={<ProtectedRoute><Cameras /></ProtectedRoute>}
      />
      <Route
        path="/cameras/:id/live"
        element={<ProtectedRoute><CameraLive /></ProtectedRoute>}
      />
      <Route
        path="/devices"
        element={<ProtectedRoute><Devices /></ProtectedRoute>}
      />
      <Route
        path="/events"
        element={<ProtectedRoute><Events /></ProtectedRoute>}
      />
      <Route
        path="/faces"
        element={<ProtectedRoute><Faces /></ProtectedRoute>}
      />
      <Route
        path="/settings"
        element={<ProtectedRoute><Settings /></ProtectedRoute>}
      />
      <Route
        path="/billing/success"
        element={<ProtectedRoute><BillingSuccess /></ProtectedRoute>}
      />
      <Route
        path="/admin"
        element={<ProtectedRoute requireAdmin><AdminPanel /></ProtectedRoute>}
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App bg-[#090A0F] min-h-screen text-white">
      <AuthProvider>
        <BrowserRouter>
          <AppRouter />
          <Toaster
            theme="dark"
            position="top-right"
            toastOptions={{
              style: {
                background: "#12141D",
                border: "1px solid rgba(255,255,255,0.1)",
                color: "#F9FAFB",
              },
            }}
          />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
