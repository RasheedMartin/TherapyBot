import { useQuery } from "@tanstack/react-query";
import api from "./client";

export interface PublicConfig {
  google_client_id: string | null;
  /** False until hosting and AI providers are covered by BAAs: synthetic data only. */
  phi_allowed: boolean;
}

export const usePublicConfig = () =>
  useQuery({
    queryKey: ["public-config"],
    queryFn: async () => (await api.get<PublicConfig>("config/")).data,
    staleTime: Infinity,
  });
