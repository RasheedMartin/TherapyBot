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
  ListSubheader,
  MenuItem,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import { Add } from "@mui/icons-material";
import { LineChart } from "@mui/x-charts/LineChart";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import type { Instrument, Screening, ScreeningTrend } from "../../api/types";
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

const EnterScreeningDialog = ({ clientId, open, onClose }: { clientId: number; open: boolean; onClose: () => void }) => {
  const queryClient = useQueryClient();
  const instruments = useInstruments();
  const [key, setKey] = useState("phq9");
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [date, setDate] = useState(new Date().toLocaleDateString("en-CA"));
  const instrument = instruments.data?.find((i) => i.key === key);
  const complete = instrument && instrument.items.every((_, i) => answers[i] != null);
  const total = Object.values(answers).reduce((a, b) => a + b, 0);
  const standard = instruments.data?.filter((i) => !i.custom) ?? [];
  const custom = instruments.data?.filter((i) => i.custom) ?? [];

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
            <ListSubheader>Standard</ListSubheader>
            {standard.map((i) => <MenuItem key={i.key} value={i.key}>{i.name}</MenuItem>)}
            {custom.length > 0 && <ListSubheader>Your templates</ListSubheader>}
            {custom.map((i) => <MenuItem key={i.key} value={i.key}>{i.name}</MenuItem>)}
          </TextField>
          <TextField size="small" type="date" label="Administered" value={date} onChange={(e) => setDate(e.target.value)}
                     slotProps={{ inputLabel: { shrink: true } }} sx={{ maxWidth: 200 }} />
        </Stack>
        {instrument && (
          <>
            {instrument.prompt && <Typography color="text.secondary" mb={2}>{instrument.prompt}</Typography>}
            <Stack spacing={2}>
              {instrument.items.map((item, i) => (
                <Box key={i}>
                  <Typography fontWeight={500}>{i + 1}. {item}</Typography>
                  <RadioGroup row value={answers[i] ?? ""} onChange={(e) => setAnswers((a) => ({ ...a, [i]: Number(e.target.value) }))}>
                    {instrument.options.map((o) => (
                      <FormControlLabel key={o.value} value={o.value} control={<Radio size="small" />}
                                        label={<Typography variant="body2">{o.label}</Typography>} />
                    ))}
                  </RadioGroup>
                </Box>
              ))}
            </Stack>
          </>
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
          <Button size="small" startIcon={<Add />} onClick={() => setEntering(true)}>Enter</Button>
        </Stack>
      }
    >
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
    </Panel>
  );
};
