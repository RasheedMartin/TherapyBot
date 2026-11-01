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
import { RouterLink } from "./RouterLink";
import api from "../api/client";
import type { CareTeamMember } from "../api/types";
import { formatDate } from "./practice/format";

const SCOPES = [
  { key: "share_checkins", label: "Plan progress (steps you check off)" },
  { key: "share_chat_summaries", label: "Chat summaries" },
  { key: "share_raw_chat", label: "Full chat conversations" },
] as const;

/** What one therapist can see, as switches. Safety alerts are always shared. Changes take effect immediately. */
export const SharingSwitches = ({ member }: { member: CareTeamMember }) => {
  const queryClient = useQueryClient();
  const update = useMutation({
    mutationFn: (scopes: Partial<CareTeamMember>) => api.patch(`care-team/${member.id}/`, scopes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["care-team"] });
      queryClient.invalidateQueries({ queryKey: ["therapist-overview", member.id] });
    },
  });
  return (
    <>
      <Typography variant="caption" color="text.secondary" display="block" mt={1}>
        Always shared: safety alerts (not live monitoring). You choose:
      </Typography>
      {SCOPES.map((s) => (
        <FormControlLabel key={s.key} label={s.label} sx={{ display: "flex" }}
          control={<Switch size="small" checked={member[s.key]} onChange={(e) => update.mutate({ [s.key]: e.target.checked })} />} />
      ))}
    </>
  );
};

/** Confirm ending care with a therapist. */
export const DisconnectDialog = ({
  member,
  onClose,
  onDone,
}: {
  member: CareTeamMember | null;
  onClose: () => void;
  onDone?: () => void;
}) => {
  const queryClient = useQueryClient();
  const leave = useMutation({
    mutationFn: (id: number) => api.post(`care-team/${id}/leave/`),
    onSuccess: (_, id) => {
      onClose();
      queryClient.invalidateQueries({ queryKey: ["care-team"] });
      queryClient.invalidateQueries({ queryKey: ["therapist-overview", id] });
      onDone?.();
    },
  });
  return (
    <Dialog open={!!member} onClose={onClose}>
      <DialogTitle>Disconnect from {member?.therapist_name}?</DialogTitle>
      <DialogContent>
        <DialogContentText>
          They'll immediately stop seeing anything new from TherapyBot, including check-ins and safety alerts. Notes they
          wrote in their own records stay with their practice.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button color="error" variant="contained" disabled={leave.isPending} onClick={() => member && leave.mutate(member.id)}>
          Disconnect
        </Button>
      </DialogActions>
    </Dialog>
  );
};

/** The client's therapists and exactly what each can see. */
export const CareTeamSection = () => {
  const [leaving, setLeaving] = useState<CareTeamMember | null>(null);
  const team = useQuery({ queryKey: ["care-team"], queryFn: async () => (await api.get<CareTeamMember[]>("care-team/")).data });
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
              <RouterLink to="/my-therapist" search={{ id: m.id }} fontWeight={600}>{m.therapist_name}</RouterLink>
              <Typography variant="body2" color="text.secondary">{m.practice_name} · connected {formatDate(m.consented_at)}</Typography>
            </Box>
            <Button size="small" color="error" onClick={() => setLeaving(m)}>Disconnect</Button>
          </Stack>
          <SharingSwitches member={m} />
        </Paper>
      ))}
      <DisconnectDialog member={leaving} onClose={() => setLeaving(null)} />
    </Stack>
  );
};
