import "./App.css";
import Navbar from "./components/Navbar";
import { Outlet } from "@tanstack/react-router";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UserProvider } from "./context/UserContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { useEffect } from "react";
import { setupInterceptors } from "./api/client";
const queryClient = new QueryClient();

function App() {
  const { logout } = useAuth();

  useEffect(() => {
    setupInterceptors(logout);
  }, [logout]);

  return (
    <>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <UserProvider>
            <Navbar />
            <main>
              <Outlet />
            </main>
          </UserProvider>
        </AuthProvider>
      </QueryClientProvider>
    </>
  );
}

export default App;
