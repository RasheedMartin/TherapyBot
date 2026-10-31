import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import { Add, ArrowDownward, ArrowUpward, DeleteOutline } from "@mui/icons-material";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import type { Frequency, Plan, PlanDraft, PlanStep } from "../../api/types";
import { FREQUENCIES, WEEKDAYS } from "./schedule";

interface PlanEditorProps {
  open: boolean;
  /** An existing plan to edit, or a draft (e.g. from the AI) to review before saving. */
  initial: Plan | PlanDraft | null;
  heading?: string;
  /** Where new plans are created; therapists assign homework at the client's homework endpoint. */
  createUrl?: string;
  onClose: () => void;
  onSaved: (plan: Plan) => void;
}

const emptyStep = (): PlanStep => ({ title: "", details: "", frequency: "daily", weekday: null, time_of_day: null });

export const PlanEditor = ({ open, initial, heading, createUrl = "plans/", onClose, onSaved }: PlanEditorProps) => {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("sm"));
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [steps, setSteps] = useState<PlanStep[]>([emptyStep()]);
  const existingId = initial && "id" in initial ? initial.id : null;

  useEffect(() => {
    if (!open) return;
    setTitle(initial?.title ?? "");
    setSummary(initial?.summary ?? "");
    setSteps(initial?.steps.length ? initial.steps.map((s) => ({ ...s, time_of_day: s.time_of_day?.slice(0, 5) ?? null })) : [emptyStep()]);
  }, [open, initial]);

  const save = useMutation({
    mutationFn: async () => {
      const body = {
        title: title.trim(),
        summary: summary.trim(),
        conversation: initial?.conversation ?? null,
        steps: steps
          .filter((s) => s.title.trim())
          .map(({ id, title, details, frequency, weekday, time_of_day, action }) => ({
            id,
            action: action ?? "",
            title: title.trim(),
            details: details.trim(),
            frequency,
            weekday: frequency === "weekly" ? (weekday ?? 0) : null,
            time_of_day: time_of_day || null,
          })),
      };
      const res = existingId ? await api.put<Plan>(`plans/${existingId}/`, body) : await api.post<Plan>(createUrl, body);
      return res.data;
    },
    onSuccess: (plan) => {
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      onSaved(plan);
    },
  });

  const updateStep = (i: number, patch: Partial<PlanStep>) =>
    setSteps((prev) => prev.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  const move = (i: number, delta: number) =>
    setSteps((prev) => {
      const next = [...prev];
      [next[i], next[i + delta]] = [next[i + delta], next[i]];
      return next;
    });

  const canSave = title.trim() && steps.some((s) => s.title.trim()) && !save.isPending;

  return (
    <Dialog open={open} onClose={onClose} fullScreen={fullScreen} maxWidth="md" fullWidth>
      <Box
        component="form"
        onSubmit={(e) => {
          e.preventDefault();
          if (canSave) save.mutate();
        }}
        sx={{ display: "contents" }}
      >
        <DialogTitle>{heading ?? (existingId ? "Edit plan" : "New plan")}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2.5}>
            {!existingId && initial && (
              <Alert severity="info">Here's a starting point based on your conversation. Change anything that doesn't fit.</Alert>
            )}
            <TextField label="Plan name" value={title} onChange={(e) => setTitle(e.target.value)} required inputProps={{ maxLength: 120 }} />
            <TextField
              label="What's this plan for?"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              multiline
              minRows={2}
              inputProps={{ maxLength: 1000 }}
            />
            <Typography variant="subtitle1" fontWeight={600}>
              Steps
            </Typography>
            {steps.map((step, i) => (
              <Paper key={step.id ?? `new-${i}`} variant="outlined" sx={{ p: 2, borderRadius: 3 }}>
                <Stack spacing={2}>
                  <Stack direction="row" spacing={1} alignItems="flex-start">
                    <TextField
                      label={`Step ${i + 1}`}
                      placeholder="e.g. 5-minute walk after breakfast"
                      value={step.title}
                      onChange={(e) => updateStep(i, { title: e.target.value })}
                      inputProps={{ maxLength: 160 }}
                    />
                    <Stack direction="row">
                      <Tooltip title="Move up">
                        <span>
                          <IconButton size="small" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Move step up">
                            <ArrowUpward fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Move down">
                        <span>
                          <IconButton
                            size="small"
                            disabled={i === steps.length - 1}
                            onClick={() => move(i, 1)}
                            aria-label="Move step down"
                          >
                            <ArrowDownward fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Remove step">
                        <span>
                          <IconButton
                            size="small"
                            disabled={steps.length === 1}
                            onClick={() => setSteps((prev) => prev.filter((_, idx) => idx !== i))}
                            aria-label="Remove step"
                          >
                            <DeleteOutline fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Stack>
                  </Stack>
                  <TextField
                    size="small"
                    label="Details (optional)"
                    value={step.details}
                    onChange={(e) => updateStep(i, { details: e.target.value })}
                  />
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                    <TextField
                      select
                      size="small"
                      label="How often"
                      value={step.frequency}
                      onChange={(e) => {
                        const frequency = e.target.value as Frequency;
                        updateStep(i, { frequency, weekday: frequency === "weekly" ? (step.weekday ?? 0) : null });
                      }}
                    >
                      {FREQUENCIES.map((f) => (
                        <MenuItem key={f.value} value={f.value}>
                          {f.label}
                        </MenuItem>
                      ))}
                    </TextField>
                    {step.frequency === "weekly" && (
                      <TextField
                        select
                        size="small"
                        label="Day"
                        value={step.weekday ?? 0}
                        onChange={(e) => updateStep(i, { weekday: Number(e.target.value) })}
                      >
                        {WEEKDAYS.map((d, idx) => (
                          <MenuItem key={d} value={idx}>
                            {d}
                          </MenuItem>
                        ))}
                      </TextField>
                    )}
                    <TextField
                      size="small"
                      type="time"
                      label="Time (optional)"
                      value={step.time_of_day ?? ""}
                      onChange={(e) => updateStep(i, { time_of_day: e.target.value || null })}
                      InputLabelProps={{ shrink: true }}
                    />
                  </Stack>
                </Stack>
              </Paper>
            ))}
            <Button
              startIcon={<Add />}
              onClick={() => setSteps((prev) => [...prev, emptyStep()])}
              disabled={steps.length >= 12}
              sx={{ alignSelf: "flex-start" }}
            >
              Add step
            </Button>
            <Typography variant="caption" color="text.secondary">
              Small steps you can do even on a hard day tend to stick best.
            </Typography>
            {save.isError && <Alert severity="error">{getErrorMessage(save.error)}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={!canSave}>
            {save.isPending ? "Saving…" : existingId ? "Save changes" : "Save plan"}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};
