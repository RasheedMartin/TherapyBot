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
  Radio,
  RadioGroup,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useTheme,
} from "@mui/material";
import { Add } from "@mui/icons-material";
import { LineChart } from "@mui/x-charts/LineChart";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import type { Instrument, Screening, ScreeningTrend } from "../../api/types";
import { formatDate } from "./format";
import { Panel } from "./AssistantPanels";

const EnterScreeningDialog = ({ clientId, open, onClose }: { clientId: number; open: boolean; onClose: () => void }) => {
  const queryClient = useQueryClient();
  const instruments = useQuery({
    queryKey: ["instruments"],
    queryFn: async () => (await api.get<Instrument[]>("screenings/instruments/")).data,
    staleTime: Infinity,
  });
  const [key, setKey] = useState<"phq9" | "gad7">("phq9");
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
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
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} mb={2} alignItems={{ sm: "center" }}>
          <ToggleButtonGroup exclusive size="small" value={key} onChange={(_, v) => { if (v) { setKey(v); setAnswers({}); } }}>
            <ToggleButton value="phq9">PHQ-9</ToggleButton>
            <ToggleButton value="gad7">GAD-7</ToggleButton>
          </ToggleButtonGroup>
          <TextField size="small" type="date" label="Administered" value={date} onChange={(e) => setDate(e.target.value)}
                     InputLabelProps={{ shrink: true }} sx={{ maxWidth: 200 }} />
        </Stack>
        {instrument && (
          <>
            <Typography color="text.secondary" mb={2}>{instrument.prompt}</Typography>
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
          Total so far: {total}{instrument ? ` / ${instrument.max_total}` : ""}
        </Typography>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={!complete || save.isPending} onClick={() => save.mutate()}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export const ScreeningsPanel = ({ clientId }: { clientId: number }) => {
  const theme = useTheme();
  const [entering, setEntering] = useState(false);
  const data = useQuery({
    queryKey: ["screenings", clientId],
    queryFn: async () =>
      (await api.get<{ screenings: Screening[]; trends: ScreeningTrend[] }>(`practice/clients/${clientId}/screenings/`)).data,
  });
  const series = (["phq9", "gad7"] as const)
    .map((key) => ({ key, points: (data.data?.screenings ?? []).filter((s) => s.instrument === key).reverse() }))
    .filter((s) => s.points.length);

  return (
    <Panel title="Screenings" action={<Button size="small" startIcon={<Add />} onClick={() => setEntering(true)}>Enter</Button>}>
      {data.data && series.length === 0 && <Typography color="text.secondary">No PHQ-9 or GAD-7 results yet.</Typography>}
      {series.map(({ key, points }) => {
        const trend = data.data?.trends.find((t) => t.instrument === (key === "phq9" ? "PHQ-9" : "GAD-7"));
        return (
          <Box key={key} mb={2}>
            <Typography fontWeight={600}>
              {key === "phq9" ? "PHQ-9" : "GAD-7"}: {trend?.latest_total} ({trend?.latest_severity})
              {trend?.change != null && (
                <Typography component="span" color={trend.change < 0 ? "success.main" : trend.change > 0 ? "warning.main" : "text.secondary"} ml={1}>
                  {trend.change > 0 ? "+" : ""}{trend.change} since {formatDate(trend.previous_date)}
                </Typography>
              )}
            </Typography>
            {points.length > 1 && (
              <LineChart
                height={180}
                margin={{ left: 0, right: 16, top: 16, bottom: 0 }}
                xAxis={[{
                  scaleType: "point",
                  data: points.map((p) => new Date(`${p.administered_on}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric" })),
                }]}
                yAxis={[{ min: 0, max: key === "phq9" ? 27 : 21, width: 32 }]}
                series={[{ data: points.map((p) => p.total), color: theme.palette.primary.main, label: "Total" }]}
                hideLegend
              />
            )}
          </Box>
        );
      })}
      <Typography variant="caption" color="text.secondary">Lower is better. Bands: 5 mild · 10 moderate · 15+ severe.</Typography>
      <EnterScreeningDialog clientId={clientId} open={entering} onClose={() => setEntering(false)} />
    </Panel>
  );
};
