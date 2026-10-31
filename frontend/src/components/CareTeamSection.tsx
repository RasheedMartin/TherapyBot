import { useState } from "react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControlLabel,
  Paper,
  Stack,
  Switch,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import type { CareTeamMember } from "../api/types";
import { formatDate } from "./practice/format";

const SCOPES = [
  { key: "share_checkins", label: "Plan check-ins" },
  { key: "share_chat_summaries", label: "Chat summaries" },
  { key: "share_raw_chat", label: "Full chat conversations" },
] as const;

/** The client's therapists and exactly what each can see. Changes take effect immediately. */
export const CareTeamSection = () => {
  const queryClient = useQueryClient();
  const [leaving, setLeaving] = useState<CareTeamMember | null>(null);
  const team = useQuery({ queryKey: ["care-team"], queryFn: async () => (await api.get<CareTeamMember[]>("care-team/")).data });
  const update = useMutation({
    mutationFn: ({ id, ...scopes }: { id: number } & Partial<CareTeamMember>) => api.patch(`care-team/${id}/`, scopes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["care-team"] }),
  });
  const leave = useMutation({
    mutationFn: (id: number) => api.post(`care-team/${id}/leave/`),
    onSuccess: () => { setLeaving(null); queryClient.invalidateQueries({ queryKey: ["care-team"] }); },
  });
  const active = team.data?.filter((m) => m.status === "active") ?? [];

  if (!team.data) return null;
  return (
    <Stack spacing={2}>
      {active.length === 0 && (
        <Typography color="text.secondary">
          You're not connected with a therapist. If yours uses TherapyBot, they can invite you by email.
        </Typography>
      )}
      {active.map((m) => (
        <Paper key={m.id} variant="outlined" sx={{ p: 2, borderRadius: 3 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
            <Box>
              <Typography fontWeight={600}>{m.therapist_name}</Typography>
              <Typography variant="body2" color="text.secondary">{m.practice_name} · connected {formatDate(m.consented_at)}</Typography>
            </Box>
            <Button size="small" color="error" onClick={() => setLeaving(m)}>Disconnect</Button>
          </Stack>
          <Typography variant="caption" color="text.secondary" display="block" mt={1}>
            Always shared: safety alerts (not live monitoring). You choose:
          </Typography>
          {SCOPES.map((s) => (
            <FormControlLabel key={s.key} label={s.label}
              control={<Switch size="small" checked={m[s.key]} onChange={(e) => update.mutate({ id: m.id, [s.key]: e.target.checked })} />} />
          ))}
        </Paper>
      ))}
      <Dialog open={!!leaving} onClose={() => setLeaving(null)}>
        <DialogTitle>Disconnect from {leaving?.therapist_name}?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            They'll immediately stop seeing anything new from TherapyBot, including check-ins and safety alerts. Notes they
            wrote in their own records stay with their practice.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLeaving(null)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={() => leaving && leave.mutate(leaving.id)}>Disconnect</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
};
