import { useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage, getFieldErrors } from "../../api/client";
import { MODALITIES, type Modality, type PracticeClient, type SessionStatus } from "../../api/types";

const localToday = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const REPEATS = [0, 3, 5, 7, 11]; // extra weekly sessions after the first

/**
 * Add a session: schedule one ahead (optionally weekly), or record one that already happened.
 * With `clientId` the client is fixed (client page); without it the therapist picks one (schedule).
 */
export const ScheduleSessionDialog = ({
  open,
  onClose,
  clientId,
  initialDate,
}: {
  open: boolean;
  onClose: () => void;
  clientId?: number;
  initialDate?: string;
}) => {
  const queryClient = useQueryClient();
  const [client, setClient] = useState<number | "">(clientId ?? "");
  const [date, setDate] = useState(initialDate ?? localToday());
  const [time, setTime] = useState("10:00");
  const [duration, setDuration] = useState(50);
  const [modality, setModality] = useState<Modality>("cbt");
  const [repeat, setRepeat] = useState(0);
  const past = date < localToday();
  const status: SessionStatus = past ? "completed" : "scheduled";

  const clients = useQuery({
    queryKey: ["practice-clients"],
    queryFn: async () => (await api.get<PracticeClient[]>("practice/clients/")).data,
    enabled: open && clientId == null,
  });
  const active = clients.data?.filter((c) => c.relationship?.status === "active") ?? [];

  const create = useMutation({
    mutationFn: () =>
      api.post(`practice/clients/${client}/sessions/`, {
        date,
        start_time: time || null,
        duration_minutes: duration,
        modality,
        status,
        repeat_weeks: past ? 0 : repeat,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule"] });
      queryClient.invalidateQueries({ queryKey: ["timeline", client] });
      onClose();
    },
  });
  const errors = getFieldErrors(create.error);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{past ? "Record a past session" : "Schedule a session"}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {clientId == null && (
            <TextField select label="Client" value={client} onChange={(e) => setClient(Number(e.target.value))}
                       helperText={clients.data && !active.length ? "No connected clients yet." : undefined}>
              {active.map((c) => <MenuItem key={c.id} value={c.id}>{c.display_name}</MenuItem>)}
            </TextField>
          )}
          <Stack direction="row" spacing={2}>
            <TextField type="date" label="Date" value={date} onChange={(e) => setDate(e.target.value)} sx={{ flex: 1 }}
                       slotProps={{ inputLabel: { shrink: true } }} error={!!errors.date} helperText={errors.date} />
            <TextField type="time" label="Time" value={time} onChange={(e) => setTime(e.target.value)} sx={{ width: 130 }}
                       slotProps={{ inputLabel: { shrink: true } }} />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField select label="Length" value={duration} onChange={(e) => setDuration(Number(e.target.value))} sx={{ flex: 1 }}
                       error={!!errors.duration_minutes} helperText={errors.duration_minutes}>
              {[30, 45, 50, 60, 90].map((m) => <MenuItem key={m} value={m}>{m} minutes</MenuItem>)}
            </TextField>
            <TextField select label="Modality" value={modality} onChange={(e) => setModality(e.target.value as Modality)} sx={{ flex: 1 }}>
              {MODALITIES.map((m) => <MenuItem key={m.value} value={m.value}>{m.label}</MenuItem>)}
            </TextField>
          </Stack>
          {!past && (
            <TextField select label="Repeat" value={repeat} onChange={(e) => setRepeat(Number(e.target.value))}>
              {REPEATS.map((r) => (
                <MenuItem key={r} value={r}>{r === 0 ? "Doesn't repeat" : `Weekly, ${r + 1} sessions`}</MenuItem>
              ))}
            </TextField>
          )}
          {create.isError && !Object.keys(errors).length && <Alert severity="error">{getErrorMessage(create.error)}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => create.mutate()} disabled={create.isPending || client === ""}>
          {past ? "Add" : "Schedule"}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
