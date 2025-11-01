import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";

// Define context shape
interface UserContextType {
  user: any | null;
  setUser: Dispatch<SetStateAction<null>>;
  isLoading: boolean;
  error: unknown;
  refetch: () => {} | null | undefined;
}

// Default value
const UserContext = createContext<UserContextType>({
  user: null,
  setUser: () => null,
  isLoading: true,
  error: null,
  refetch: () => {},
});

// Provider component
export const UserProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState(null);

  const {
    data: userData,
    error,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["current_user_info"],
    queryFn: () => api.get("current_user"),
    staleTime: 2 * 60,
    retry: false,
    enabled: false,
  });

  useEffect(() => {
    if (userData) {
      setUser(userData.data);
    }

    if (error) {
      setUser(null);
    }
  }, [userData]);

  return (
    <UserContext.Provider value={{ user, setUser, isLoading, error, refetch }}>
      {children}
    </UserContext.Provider>
  );
};

// Custom hook for easy access
export const useUser = () => useContext(UserContext);
