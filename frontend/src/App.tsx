import "./App.css";
import Navbar from "./components/Navbar";
import { Outlet } from "@tanstack/react-router";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UserProvider } from "./context/UserContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { useEffect } from "react";
import { setupInterceptors } from "./api/client";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";

const queryClient = new QueryClient();

function AppInner() {
  const { logout } = useAuth();

  useEffect(() => {
    setupInterceptors(logout);
  }, [logout]);

  return (
    <>
      <Navbar />
      <main>
        <Outlet />
        <TanStackRouterDevtools position="bottom-right" />
      </main>
    </>
  );
}

function App() {
  return (
    <>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <UserProvider>
            <Navbar />
            <AppInner />
          </UserProvider>
        </AuthProvider>
      </QueryClientProvider>
    </>
  );
}

export default App;
