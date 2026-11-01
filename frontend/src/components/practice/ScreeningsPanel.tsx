import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  ListSubheader,
  MenuItem,
  Stack,
  Tooltip,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import { Add, Close, SendOutlined } from "@mui/icons-material";
import { LineChart } from "@mui/x-charts/LineChart";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import {
  CHECK_IN_REPEATS,
  type CheckInAssignment,
  type CheckInRepeat,
  type Instrument,
  type Screening,
  type ScreeningTrend,
} from "../../api/types";
import { ScreeningQuestions } from "../screenings/ScreeningQuestions";
import { LinkButton } from "../RouterLink";
import { formatDate } from "./format";
import { Panel } from "./AssistantPanels";

const INSTRUMENTS_KEY = ["instruments"];

const useInstruments = () =>
  useQuery({
    queryKey: INSTRUMENTS_KEY,
    queryFn: async () => (await api.get<Instrument[]>("screenings/instruments/")).data,
    staleTime: 5 * 60 * 1000,
  });

/** Menu items for a screening picker: the standard ones, then the practice's own templates. */
const instrumentOptions = (instruments: Instrument[] = []) => {
  const custom = instruments.filter((i) => i.custom);
  return [
    <ListSubheader key="standard">Standard</ListSubheader>,
    ...instruments.filter((i) => !i.custom).map((i) => <MenuItem key={i.key} value={i.key}>{i.name}</MenuItem>),
    ...(custom.length ? [<ListSubheader key="custom">Your templates</ListSubheader>] : []),
    ...custom.map((i) => <MenuItem key={i.key} value={i.key}>{i.name}</MenuItem>),
  ];
};

const today = () => new Date().toLocaleDateString("en-CA");

const SendCheckInDialog = ({ clientId, open, onClose }: { clientId: number; open: boolean; onClose: () => void }) => {
  const queryClient = useQueryClient();
  const instruments = useInstruments();
  const [key, setKey] = useState("phq9");
  const [repeat, setRepeat] = useState<CheckInRepeat>("once");
  const [start, setStart] = useState(today());
  const [note, setNote] = useState("");

  const send = useMutation({
    mutationFn: async () =>
      (await api.post<CheckInAssignment & { emailed: boolean }>(`practice/clients/${clientId}/checkins/`, {
        instrument: key, repeat, due_on: start, note,
      })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["checkins", clientId] });
      setNote("");
      onClose();
    },
  });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Send a check-in</DialogTitle>
      <DialogContent>
        <Typography color="text.secondary" mb={2}>
          Your client completes it from their TherapyBot home and gets an email when it's ready. Results land here,
          and safety answers raise a flag like any screening.
        </Typography>
        <Stack spacing={2}>
          <TextField select label="Screening" value={key} onChange={(e) => setKey(e.target.value)}>
            {instrumentOptions(instruments.data)}
          </TextField>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField select label="Repeat" value={repeat} sx={{ flex: 1 }}
                       onChange={(e) => setRepeat(e.target.value as CheckInRepeat)}>
              {CHECK_IN_REPEATS.map((r) => <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>)}
            </TextField>
            <TextField type="date" label={repeat === "once" ? "Send on" : "First one on"} value={start} sx={{ flex: 1 }}
                       onChange={(e) => setStart(e.target.value)}
                       slotProps={{ inputLabel: { shrink: true }, htmlInput: { min: today() } }} />
          </Stack>
          <TextField label="Note to your client (optional)" value={note} onChange={(e) => setNote(e.target.value)}
                     multiline minRows={2} slotProps={{ htmlInput: { maxLength: 300 } }}
                     helperText="Shown with the check-in in the app, not in the email." />
        </Stack>
        {send.isError && <Alert severity="error" sx={{ mt: 2 }}>{getErrorMessage(send.error)}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={send.isPending} onClick={() => send.mutate()}>
          {start === today() ? "Send now" : "Schedule"}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

const repeatLabel = (repeat: CheckInRepeat) => CHECK_IN_REPEATS.find((r) => r.value === repeat)?.label ?? repeat;

/** Check-ins sent to this client that are still going, each with a way to stop it. */
const ActiveCheckIns = ({ clientId }: { clientId: number }) => {
  const queryClient = useQueryClient();
  const assignments = useQuery({
    queryKey: ["checkins", clientId],
    queryFn: async () => (await api.get<CheckInAssignment[]>(`practice/clients/${clientId}/checkins/`)).data,
  });
  const stop = useMutation({
    mutationFn: (id: number) => api.delete(`practice/clients/${clientId}/checkins/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["checkins", clientId] }),
  });
  const active = assignments.data?.filter((a) => a.active) ?? [];
  if (!active.length) return null;

  return (
    <Box mb={2} pb={1.5} sx={{ borderBottom: 1, borderColor: "divider" }}>
      <Typography variant="body2" fontWeight={600} mb={0.5}>Sent to client</Typography>
      {active.map((a) => (
        <Stack key={a.id} direction="row" alignItems="center" spacing={1}>
          <Typography variant="body2" sx={{ flex: 1 }}>
            {a.instrument_name}, {repeatLabel(a.repeat).toLowerCase()}.{" "}
            <Typography component="span" variant="body2" color="text.secondary">
              {a.due_on <= today() ? "Waiting for them" : `Next on ${formatDate(a.due_on)}`}
              {a.last_completed_on && `, last done ${formatDate(a.last_completed_on)}`}
            </Typography>
          </Typography>
          <Tooltip title={`Stop sending ${a.instrument_name}`} describeChild>
            <IconButton size="small" aria-label={`Stop sending ${a.instrument_name}`} disabled={stop.isPending}
                        onClick={() => stop.mutate(a.id)}>
              <Close fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      ))}
    </Box>
  );
};

const EnterScreeningDialog = ({ clientId, open, onClose }: { clientId: number; open: boolean; onClose: () => void }) => {
  const queryClient = useQueryClient();
  const instruments = useInstruments();
  const [key, setKey] = useState("phq9");
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [date, setDate] = useState(today());
  const instrument = instruments.data?.find((i) => i.key === key);
  const complete = instrument && instrument.items.every((_, i) => answers[i] != null);
  const total = Object.values(answers).reduce((a, b) => a + b, 0);

  const save = useMutation({
    mutationFn: async () =>
      (await api.post<Screening & { flagged: boolean }>(`practice/clients/${clientId}/screenings/`, {
        instrument: key,
        responses: instrument!.items.map((_, i) => answers[i]),
        administered_on: date,
      })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["screenings", clientId] });
      queryClient.invalidateQueries({ queryKey: ["risk-flags"] });
      setAnswers({});
      onClose();
    },
  });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Enter a screening</DialogTitle>
      <DialogContent dividers>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} mb={2}>
          <TextField select size="small" label="Screening" value={key} sx={{ minWidth: 260 }}
                     onChange={(e) => { setKey(e.target.value); setAnswers({}); }}>
            {instrumentOptions(instruments.data)}
          </TextField>
          <TextField size="small" type="date" label="Administered" value={date} onChange={(e) => setDate(e.target.value)}
                     slotProps={{ inputLabel: { shrink: true } }} sx={{ maxWidth: 200 }} />
        </Stack>
        {instrument && (
          <ScreeningQuestions instrument={instrument} answers={answers}
                              onAnswer={(i, v) => setAnswers((a) => ({ ...a, [i]: v }))} />
        )}
        {save.isError && <Alert severity="error" sx={{ mt: 2 }}>{getErrorMessage(save.error)}</Alert>}
      </DialogContent>
      <DialogActions>
        <Typography variant="body2" color="text.secondary" sx={{ mr: "auto", ml: 2 }}>
          Total so far: {total}{instrument ? ` of ${instrument.max_total}` : ""}
        </Typography>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={!complete || save.isPending} onClick={() => save.mutate()}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
};

const bandsCaption = (instrument?: Instrument) => {
  if (!instrument?.bands.length) return "";
  return instrument.bands.map((b, i) => `${i === 0 ? "" : "from "}${b.min} ${b.label}`).join(", ");
};

export const ScreeningsPanel = ({ clientId }: { clientId: number }) => {
  const theme = useTheme();
  const [entering, setEntering] = useState(false);
  const [sending, setSending] = useState(false);
  const instruments = useInstruments();
  const data = useQuery({
    queryKey: ["screenings", clientId],
    queryFn: async () =>
      (await api.get<{ screenings: Screening[]; trends: ScreeningTrend[] }>(`practice/clients/${clientId}/screenings/`)).data,
  });
  const trends = data.data?.trends ?? [];

  return (
    <Panel
      title="Screenings"
      action={
        <Stack direction="row" spacing={0.5}>
          <LinkButton to="/practice/templates" size="small">Templates</LinkButton>
          <Button size="small" startIcon={<SendOutlined />} onClick={() => setSending(true)}>Send</Button>
          <Button size="small" startIcon={<Add />} onClick={() => setEntering(true)}>Enter</Button>
        </Stack>
      }
    >
      <ActiveCheckIns clientId={clientId} />
      {data.data && trends.length === 0 && <Typography color="text.secondary">No screening results yet.</Typography>}
      {trends.map((trend) => {
        const points = (data.data?.screenings ?? []).filter((s) => s.instrument === trend.key).reverse();
        const instrument = instruments.data?.find((i) => i.key === trend.key);
        return (
          <Box key={trend.key} mb={2}>
            <Typography fontWeight={600}>
              {trend.instrument}: {trend.latest_total}{trend.latest_severity && ` (${trend.latest_severity})`}
              {trend.change != null && (
                // Lower is better on PHQ-9 / GAD-7; a template's direction isn't known, so its change stays neutral
                <Typography component="span" ml={1}
                            color={instrument?.custom || trend.change === 0 ? "text.secondary" : trend.change < 0 ? "success.main" : "warning.main"}>
                  {trend.change > 0 ? "+" : ""}{trend.change} since {formatDate(trend.previous_date)}
                </Typography>
              )}
            </Typography>
            {points.length > 1 && (
              <LineChart
                height={170}
                margin={{ left: 0, right: 28, top: 16, bottom: 0 }}
                xAxis={[{
                  scaleType: "point",
                  data: points.map((p) => new Date(`${p.administered_on}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric" })),
                }]}
                yAxis={[{ min: 0, max: trend.max_total, width: 32 }]}
                series={[{ data: points.map((p) => p.total), color: theme.palette.primary.main, label: "Total" }]}
                hideLegend
              />
            )}
            {bandsCaption(instrument) && (
              <Typography variant="caption" color="text.secondary">Ranges: {bandsCaption(instrument)}.</Typography>
            )}
          </Box>
        );
      })}
      <EnterScreeningDialog clientId={clientId} open={entering} onClose={() => setEntering(false)} />
      <SendCheckInDialog clientId={clientId} open={sending} onClose={() => setSending(false)} />
    </Panel>
  );
};
