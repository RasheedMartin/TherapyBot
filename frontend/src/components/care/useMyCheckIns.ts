import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import type { MyCheckIn } from "../../api/types";

export const MY_CHECKINS_KEY = ["my-checkins"];

export const useMyCheckIns = () =>
  useQuery({
    queryKey: MY_CHECKINS_KEY,
    queryFn: async () => (await api.get<MyCheckIn[]>("screenings/checkins/")).data,
  });
