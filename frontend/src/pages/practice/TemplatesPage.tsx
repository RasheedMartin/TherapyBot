import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { Add, DeleteOutline } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage, getFieldErrors } from "../../api/client";
import type { AnswerOption, ScreeningTemplate } from "../../api/types";
import { SyntheticDataBanner } from "../../components/practice/SyntheticDataBanner";

const KEY = ["screening-templates"];

const SCALES: { key: string; label: string; options: AnswerOption[] }[] = [
  { key: "frequency", label: "How often (Not at all to Nearly every day)", options: [
    { value: 0, label: "Not at all" }, { value: 1, label: "Several days" },
    { value: 2, label: "More than half the days" }, { value: 3, label: "Nearly every day" }] },
  { key: "agreement", label: "Agreement (Strongly disagree to Strongly agree)", options: [
    { value: 0, label: "Strongly disagree" }, { value: 1, label: "Disagree" }, { value: 2, label: "Neutral" },
    { value: 3, label: "Agree" }, { value: 4, label: "Strongly agree" }] },
  { key: "severity", label: "Severity (None to Extreme)", options: [
    { value: 0, label: "None" }, { value: 1, label: "Mild" }, { value: 2, label: "Moderate" },
    { value: 3, label: "Severe" }, { value: 4, label: "Extreme" }] },
  { key: "rating", label: "Rating from 0 to 10", options: Array.from({ length: 11 }, (_, i) => ({ value: i, label: String(i) })) },
];

type Draft = Omit<ScreeningTemplate, "id" | "key" | "archived" | "results" | "updated_at"> & { id?: number };

const blank = (): Draft => ({
  name: "", prompt: "", items: [""], options: SCALES[0].options, bands: [], risk_item: null, risk_min: 1,
});

/** Create or edit a template. Once it has results, its questions and answers are locked. */
const TemplateEditor = ({ initial, locked, onClose }: { initial: Draft; locked: boolean; onClose: () => void }) => {
  const queryClient = useQueryClient();
  const [t, setT] = useState<Draft>(initial);
  const scale = SCALES.find((s) => JSON.stringify(s.options) === JSON.stringify(t.options))?.key ?? "custom";
  const set = (patch: Partial<Draft>) => setT((current) => ({ ...current, ...patch }));
  const save = useMutation({
    mutationFn: async () => {
      const body = { ...t, items: t.items.map((i) => i.trim()).filter(Boolean) };
      return t.id ? api.patch(`practice/screening-templates/${t.id}/`, locked ? { name: t.name, prompt: t.prompt } : body)
                  : api.post("practice/screening-templates/", body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEY });
      queryClient.invalidateQueries({ queryKey: ["instruments"] });
      onClose();
    },
  });
  const errors = getFieldErrors(save.error);
  const maxTotal = Math.max(...t.options.map((o) => o.value), 0) * t.items.filter((i) => i.trim()).length;

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{t.id ? "Edit template" : "New screening template"}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2.5}>
          {locked && (
            <Alert severity="info">
              This template has results, so its questions and answers are locked and past scores stay comparable. Duplicate
              it to change them.
            </Alert>
          )}
          <TextField label="Name" value={t.name} onChange={(e) => set({ name: e.target.value })} required
                     error={!!errors.name} helperText={errors.name ?? "Clients see this name."} />
          <TextField label="Instructions" value={t.prompt} onChange={(e) => set({ prompt: e.target.value })} multiline minRows={2}
                     placeholder="e.g. Think about the past week." />

          <Box>
            <Typography variant="subtitle2" gutterBottom>Questions</Typography>
            <Stack spacing={1}>
              {t.items.map((item, i) => (
                <Stack key={i} direction="row" spacing={1} alignItems="center">
                  <Typography color="text.secondary" sx={{ width: 24, textAlign: "right" }}>{i + 1}.</Typography>
                  <TextField size="small" value={item} disabled={locked} placeholder="Question"
                             onChange={(e) => set({ items: t.items.map((x, j) => (j === i ? e.target.value : x)) })} />
                  <Tooltip title="Remove question" describeChild>
                    <span>
                      <IconButton size="small" aria-label={`Remove question ${i + 1}`} disabled={locked || t.items.length === 1}
                                  onClick={() => set({ items: t.items.filter((_, j) => j !== i),
                                                       risk_item: t.risk_item === i ? null : t.risk_item != null && t.risk_item > i ? t.risk_item - 1 : t.risk_item })}>
                        <DeleteOutline fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                </Stack>
              ))}
            </Stack>
            {!locked && <Button size="small" startIcon={<Add />} sx={{ mt: 1 }} onClick={() => set({ items: [...t.items, ""] })}>Add question</Button>}
            {errors.items && <Typography color="error" variant="body2">{errors.items}</Typography>}
          </Box>

          <Box>
            <Typography variant="subtitle2" gutterBottom>Answers (the same for every question)</Typography>
            <TextField select size="small" value={scale} disabled={locked} sx={{ maxWidth: 420 }}
                       onChange={(e) => {
                         const preset = SCALES.find((s) => s.key === e.target.value);
                         if (preset) set({ options: preset.options, risk_min: preset.options[1].value });
                       }}>
              {SCALES.map((s) => <MenuItem key={s.key} value={s.key}>{s.label}</MenuItem>)}
              {scale === "custom" && <MenuItem value="custom">Custom answers</MenuItem>}
            </TextField>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap mt={1}>
              {t.options.map((o) => (
                <Chip key={o.value} size="small" variant="outlined" label={o.label === String(o.value) ? o.label : `${o.value}: ${o.label}`} />
              ))}
            </Stack>
            {errors.options && <Typography color="error" variant="body2">{errors.options}</Typography>}
          </Box>

          <Box>
            <Typography variant="subtitle2">Score ranges (optional)</Typography>
            <Typography variant="body2" color="text.secondary" mb={1}>
              Totals run from 0 to {maxTotal}. Label ranges to see them on the chart, e.g. 0 low, 6 medium, 10 high.
            </Typography>
            <Stack spacing={1}>
              {t.bands.map((b, i) => (
                <Stack key={i} direction="row" spacing={1} alignItems="center">
                  <TextField size="small" type="number" label="From" value={b.min} sx={{ width: 100 }}
                             onChange={(e) => set({ bands: t.bands.map((x, j) => (j === i ? { ...x, min: Number(e.target.value) } : x)) })} />
                  <TextField size="small" label="Label" value={b.label}
                             onChange={(e) => set({ bands: t.bands.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)) })} />
                  <IconButton size="small" aria-label="Remove range" onClick={() => set({ bands: t.bands.filter((_, j) => j !== i) })}>
                    <DeleteOutline fontSize="small" />
                  </IconButton>
                </Stack>
              ))}
            </Stack>
            <Button size="small" startIcon={<Add />} sx={{ mt: 1 }}
                    onClick={() => set({ bands: [...t.bands, { min: t.bands.length ? t.bands[t.bands.length - 1].min + 1 : 0, label: "" }] })}>
              Add range
            </Button>
            {errors.bands && <Typography color="error" variant="body2">{errors.bands}</Typography>}
          </Box>

          <Box>
            <Typography variant="subtitle2">Safety question (optional)</Typography>
            <Typography variant="body2" color="text.secondary" mb={1}>
              Answers at or above the level you choose raise a safety flag in your inbox, like PHQ-9 question 9.
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
              <TextField select size="small" label="Question" value={t.risk_item ?? ""} disabled={locked} sx={{ minWidth: 240 }}
                         onChange={(e) => set({ risk_item: e.target.value === "" ? null : Number(e.target.value) })}>
                <MenuItem value="">None</MenuItem>
                {t.items.map((item, i) => <MenuItem key={i} value={i}>{i + 1}. {item.slice(0, 50) || "(empty)"}</MenuItem>)}
              </TextField>
              {t.risk_item != null && (
                <TextField select size="small" label="Flag when the answer is at least" value={t.risk_min} disabled={locked} sx={{ minWidth: 240 }}
                           onChange={(e) => set({ risk_min: Number(e.target.value) })} error={!!errors.risk_min} helperText={errors.risk_min}>
                  {t.options.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
                </TextField>
              )}
            </Stack>
          </Box>
          {save.isError && !Object.keys(errors).length && <Alert severity="error">{getErrorMessage(save.error)}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={save.isPending || !t.name.trim() || !t.items.some((i) => i.trim())} onClick={() => save.mutate()}>
          {t.id ? "Save changes" : "Create template"}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

/** The practice's own screening templates, alongside the standard PHQ-9 and GAD-7. */
export const TemplatesPage = () => {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<{ draft: Draft; locked: boolean } | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const templates = useQuery({
    queryKey: KEY,
    queryFn: async () => (await api.get<ScreeningTemplate[]>("practice/screening-templates/")).data,
  });
  const archive = useMutation({
    mutationFn: (t: ScreeningTemplate) => api.patch(`practice/screening-templates/${t.id}/`, { archived: !t.archived }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEY });
      queryClient.invalidateQueries({ queryKey: ["instruments"] });
    },
  });
  const shown = templates.data?.filter((t) => showArchived || !t.archived) ?? [];
  const toDraft = (t: ScreeningTemplate, copy = false): Draft => ({
    id: copy ? undefined : t.id, name: copy ? `${t.name} (copy)` : t.name, prompt: t.prompt, items: [...t.items],
    options: t.options, bands: t.bands, risk_item: t.risk_item, risk_min: t.risk_min,
  });

  return (
    <Container maxWidth="md" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2} mb={3}>
        <Box>
          <Typography variant="h4" component="h1">Screening templates</Typography>
          <Typography color="text.secondary" mt={0.5}>
            Build your own questionnaires. They're scored, charted and flagged like PHQ-9 and GAD-7, and appear in
            prep and Ask the record.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<Add />} sx={{ flexShrink: 0 }}
                onClick={() => setEditing({ draft: blank(), locked: false })}>
          New template
        </Button>
      </Stack>
      <Stack spacing={3}>
        <SyntheticDataBanner />
        {templates.isError && <Alert severity="error">{getErrorMessage(templates.error)}</Alert>}
        {templates.isLoading && <Skeleton variant="rounded" height={120} />}
        {templates.data && (
          <Paper variant="outlined" sx={{ borderRadius: 4, overflow: "hidden" }}>
            {shown.length === 0 && (
              <Box p={3}>
                <Typography color="text.secondary">
                  No templates yet. PHQ-9 and GAD-7 are always available; create a template for anything else you track,
                  like sleep, cravings, or a measure you use in your practice.
                </Typography>
              </Box>
            )}
            {shown.map((t, i) => (
              <Stack key={t.id} direction={{ xs: "column", sm: "row" }} spacing={1.5} justifyContent="space-between"
                     alignItems={{ sm: "center" }} sx={{ p: 2.5, borderTop: i ? 1 : 0, borderColor: "divider", opacity: t.archived ? 0.6 : 1 }}>
                <Box minWidth={0}>
                  <Typography fontWeight={600}>{t.name}{t.archived && " (archived)"}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {t.items.length} {t.items.length === 1 ? "question" : "questions"}, answers {t.options[0].label.toLowerCase()} to{" "}
                    {t.options[t.options.length - 1].label.toLowerCase()}
                    {t.risk_item != null && ", with a safety question"}. {t.results ? `${t.results} results recorded.` : "Not used yet."}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1} flexShrink={0}>
                  <Button size="small" onClick={() => setEditing({ draft: toDraft(t), locked: t.results > 0 })}>Edit</Button>
                  <Button size="small" onClick={() => setEditing({ draft: toDraft(t, true), locked: false })}>Duplicate</Button>
                  <Button size="small" color={t.archived ? "primary" : "inherit"} onClick={() => archive.mutate(t)}>
                    {t.archived ? "Restore" : "Archive"}
                  </Button>
                </Stack>
              </Stack>
            ))}
          </Paper>
        )}
        {templates.data?.some((t) => t.archived) && (
          <FormControlLabel control={<Switch checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />}
                            label="Show archived templates" />
        )}
      </Stack>
      {editing && <TemplateEditor initial={editing.draft} locked={editing.locked} onClose={() => setEditing(null)} />}
    </Container>
  );
};
