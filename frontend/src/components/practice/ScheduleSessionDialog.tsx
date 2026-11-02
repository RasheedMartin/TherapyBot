import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage, getFieldErrors } from "../../api/client";
import { MODALITIES, type Modality, type PracticeClient, type SessionStatus } from "../../api/types";

const localToday = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const ORDINALS = ["first", "second", "third", "fourth", "last"];

type Frequency = "none" | "weekly" | "biweekly" | "days" | "monthly";

/** Monday = 0, matching the API. */
const weekdayOf = (iso: string) => (new Date(`${iso}T12:00:00`).getDay() + 6) % 7;
const nthOf = (iso: string) => Math.min(Math.floor((Number(iso.slice(8, 10)) - 1) / 7) + 1, 5);
const shortDate = (d: Date) => d.toLocaleDateString([], { month: "short", day: "numeric" });

/** The dates a series will land on, mirroring the server's rules, for the summary line. */
const preview = (start: string, frequency: Frequency, days: number[], ends: "count" | "until", count: number, until: string) => {
  const first = new Date(`${start}T12:00:00`);
  const last = ends === "until" && until ? new Date(`${until}T12:00:00`) : null;
  const limit = ends === "count" ? count : 52;
  const out = [first];
  const add = (d: Date) => { if ((!last || d <= last) && out.length < limit) out.push(d); };
  if (frequency === "weekly" || frequency === "biweekly") {
    const step = frequency === "weekly" ? 7 : 14;
    for (let i = 1; out.length < limit && i < 400; i++) {
      const d = new Date(first); d.setDate(first.getDate() + i * step);
      if (last && d > last) break;
      add(d);
    }
  } else if (frequency === "days") {
    const chosen = new Set([...days, weekdayOf(start)]);
    for (let i = 1; out.length < limit && i < 366; i++) {
      const d = new Date(first); d.setDate(first.getDate() + i);
      if (last && d > last) break;
      if (chosen.has((d.getDay() + 6) % 7)) add(d);
    }
  } else if (frequency === "monthly") {
    const n = nthOf(start), weekday = first.getDay();
    for (let m = 1; out.length < limit && m < 13; m++) {
      const month = new Date(first.getFullYear(), first.getMonth() + m, 1, 12);
      const d = new Date(month); d.setDate(1 + ((weekday - month.getDay() + 7) % 7));
      if (n === 5) { while (new Date(d.getFullYear(), d.getMonth(), d.getDate() + 7).getMonth() === d.getMonth()) d.setDate(d.getDate() + 7); }
      else d.setDate(d.getDate() + (n - 1) * 7);
      if (last && d > last) break;
      add(d);
    }
  }
  return out;
};

/**
 * Add a session: schedule one ahead (optionally repeating), or record one that already happened.
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
  const [frequency, setFrequency] = useState<Frequency>("none");
  const [days, setDays] = useState<number[]>([]);
  const [ends, setEnds] = useState<"count" | "until">("count");
  const [count, setCount] = useState(8);
  const [until, setUntil] = useState("");
  const past = date < localToday();
  const status: SessionStatus = past ? "completed" : "scheduled";
  const repeating = !past && frequency !== "none";
  const weekday = WEEKDAYS[weekdayOf(date)];
  const dates = repeating ? preview(date, frequency, days, ends, count, until) : [];

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
        repeat: repeating
          ? { frequency, weekdays: days, ...(ends === "count" ? { count } : { until }) }
          : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule"] });
      queryClient.invalidateQueries({ queryKey: ["practice-overview"] });
      queryClient.invalidateQueries({ queryKey: ["timeline", client] });
      onClose();
    },
  });
  const errors = getFieldErrors(create.error);
  const pattern =
    frequency === "weekly" ? `every ${weekday}`
    : frequency === "biweekly" ? `every other ${weekday}`
    : frequency === "monthly" ? `on the ${ORDINALS[nthOf(date) - 1]} ${weekday} of each month`
    : `every ${[...new Set([weekdayOf(date), ...days])].sort().map((d) => WEEKDAYS[d]).join(" and ")}`;

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
            <TextField select label="Repeat" value={frequency} onChange={(e) => setFrequency(e.target.value as Frequency)}>
              <MenuItem value="none">Doesn't repeat</MenuItem>
              <MenuItem value="weekly">Weekly on {weekday}</MenuItem>
              <MenuItem value="biweekly">Every 2 weeks on {weekday}</MenuItem>
              <MenuItem value="days">On specific days each week</MenuItem>
              <MenuItem value="monthly">Monthly on the {ORDINALS[nthOf(date) - 1]} {weekday}</MenuItem>
            </TextField>
          )}

          {repeating && frequency === "days" && (
            <Box>
              <Typography variant="body2" color="text.secondary" mb={0.75}>Days</Typography>
              <ToggleButtonGroup size="small" value={[...new Set([weekdayOf(date), ...days])]}
                                 onChange={(_, value: number[]) => setDays(value.filter((d) => d !== weekdayOf(date)))}
                                 aria-label="Days of the week">
                {WEEKDAYS.map((name, i) => (
                  <ToggleButton key={name} value={i} disabled={i === weekdayOf(date)} aria-label={name} sx={{ px: 1.25 }}>
                    {name.slice(0, 3)}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Box>
          )}

          {repeating && (
            <Box>
              <Typography variant="body2" color="text.secondary">Ends</Typography>
              <RadioGroup value={ends} onChange={(e) => setEnds(e.target.value as "count" | "until")}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <FormControlLabel value="count" control={<Radio size="small" />} label="After" sx={{ mr: 0 }} />
                  <TextField size="small" type="number" value={count} disabled={ends !== "count"} sx={{ width: 84 }}
                             onChange={(e) => setCount(Math.max(2, Math.min(52, Number(e.target.value) || 2)))}
                             slotProps={{ htmlInput: { min: 2, max: 52, "aria-label": "Number of sessions" } }} />
                  <Typography color={ends === "count" ? "text.primary" : "text.disabled"}>sessions</Typography>
                </Stack>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <FormControlLabel value="until" control={<Radio size="small" />} label="On" sx={{ mr: 0 }} />
                  <TextField size="small" type="date" value={until} disabled={ends !== "until"} sx={{ width: 180 }}
                             onChange={(e) => setUntil(e.target.value)} slotProps={{ htmlInput: { "aria-label": "End date" } }} />
                </Stack>
              </RadioGroup>
            </Box>
          )}

          {repeating && dates.length > 1 && (
            <Typography variant="body2" color="text.secondary">
              {dates.length} sessions {pattern}, {shortDate(dates[0])} to {shortDate(dates[dates.length - 1])}.
            </Typography>
          )}
          {errors.repeat && <Alert severity="warning">{errors.repeat}</Alert>}
          {create.isError && !Object.keys(errors).length && <Alert severity="error">{getErrorMessage(create.error)}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => create.mutate()}
                disabled={create.isPending || client === "" || (repeating && ends === "until" && !until)}>
          {past ? "Add" : repeating ? `Schedule ${dates.length} sessions` : "Schedule"}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
