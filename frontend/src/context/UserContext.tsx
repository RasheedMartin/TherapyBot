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

// Move hook to its own file to fix react-refresh warning
// (or keep here and suppress the warning)

interface User {
  id: number;
  username: string;
  email: string;
}

interface UserContextType {
  user: User | null;
  setUser: Dispatch<SetStateAction<User | null>>;
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
}

const UserContext = createContext<UserContextType>({
  user: null,
  setUser: () => null,
  isLoading: true,
  error: null,
  refetch: () => {},
});

export const UserProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<User | null>(null);

  const {
    data: userData,
    error,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["current_user_info"],
    queryFn: () => api.get<User>("current_user"),
    staleTime: 2 * 60,
    retry: false,
    enabled: !!localStorage.getItem("access"),
  });

  useEffect(() => {
    if (userData) {
      setUser(userData.data);
    }
    if (error) {
      setUser(null);
    }
  }, [userData, error]);

  return (
    <UserContext.Provider value={{ user, setUser, isLoading, error, refetch }}>
      {children}
    </UserContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useUser = () => useContext(UserContext);
