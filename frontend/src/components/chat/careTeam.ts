import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import type { CareTeamMember } from "../../api/types";

/** The client's active therapists. Empty for people using TherapyBot on their own. */
export const useActiveCareTeam = () => {
  const team = useQuery({
    queryKey: ["care-team"],
    queryFn: async () => (await api.get<CareTeamMember[]>("care-team/")).data,
    staleTime: 5 * 60 * 1000,
  });
  return team.data?.filter((m) => m.status === "active") ?? [];
};
