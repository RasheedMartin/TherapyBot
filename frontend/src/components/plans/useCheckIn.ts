import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../api/client";
import type { Plan, PlanStep } from "../../api/types";
import { isoDate } from "./schedule";

export const PLANS_KEY = ["plans"];

/** Mark a plan step done (or not) for a day, updating every plan view immediately. */
export const useCheckIn = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ step, day, done }: { step: PlanStep; day: Date; done: boolean }) =>
      (await api.request<Plan>({ url: `plan-steps/${step.id}/check-in/`, method: done ? "POST" : "DELETE", data: { date: isoDate(day) } }))
        .data,
    // Update the UI immediately; the server response replaces it
    onMutate: ({ step, day, done }) => {
      const date = isoDate(day);
      queryClient.setQueryData<Plan[]>(PLANS_KEY, (plans) =>
        plans?.map((p) => ({
          ...p,
          steps: p.steps.map((s) =>
            s.id !== step.id
              ? s
              : { ...s, check_ins: done ? [...(s.check_ins ?? []), date] : (s.check_ins ?? []).filter((d) => d !== date) },
          ),
        })),
      );
    },
    onSuccess: (plan) =>
      queryClient.setQueryData<Plan[]>(PLANS_KEY, (plans) => plans?.map((p) => (p.id === plan.id ? plan : p))),
    onError: () => queryClient.invalidateQueries({ queryKey: PLANS_KEY }),
  });
};

