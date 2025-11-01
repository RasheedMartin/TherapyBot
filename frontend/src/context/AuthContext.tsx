// AuthContext.tsx
import { createContext, useContext, useState, useEffect } from "react";

// Define context shape
interface AuthContextType {
  authenticated: boolean;
  login: (access: string, refresh: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  authenticated: false,
  login: () => {},
  logout: () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [authenticated, setAuthenticated] = useState(
    !!localStorage.getItem("access")
  );

  const login = (access: string, refresh: string) => {
    localStorage.setItem("access", access);
    localStorage.setItem("refresh", refresh);
    setAuthenticated(true);
  };

  const logout = () => {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    setAuthenticated(false);
  };

  // Keep state in sync with localStorage changes (optional)
  useEffect(() => {
    const handleStorageChange = () => {
      setAuthenticated(!!localStorage.getItem("access"));
    };
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  return (
    <AuthContext.Provider value={{ authenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
