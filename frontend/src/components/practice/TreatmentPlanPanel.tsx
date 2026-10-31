import { useState } from "react";
import { Alert, Box, Button, Chip, CircularProgress, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { AutoAwesomeOutlined, Verified } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import { MODALITIES, type Modality, type TreatmentPlan } from "../../api/types";
import { Panel } from "./AssistantPanels";
import { CitationChips } from "./Citations";
import { formatDate } from "./format";

export const TreatmentPlanPanel = ({ clientId }: { clientId: number }) => {
  const queryClient = useQueryClient();
  const [modality, setModality] = useState<Modality>("cbt");
  const key = ["treatment-plans", clientId];
  const plans = useQuery({
    queryKey: key,
    queryFn: async () => (await api.get<TreatmentPlan[]>(`practice/clients/${clientId}/treatment-plans/`)).data,
  });
  const draft = useMutation({
    mutationFn: () => api.post(`practice/clients/${clientId}/treatment-plans/`, { modality }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const sign = useMutation({
    mutationFn: (id: number) => api.post(`practice/clients/${clientId}/treatment-plans/${id}/sign/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const current = plans.data?.find((p) => p.status === "draft") ?? plans.data?.find((p) => p.status === "active");

  return (
    <Panel
      title="Treatment plan"
      action={
        <Stack direction="row" spacing={1}>
          <TextField select size="small" value={modality} onChange={(e) => setModality(e.target.value as Modality)} sx={{ minWidth: 120 }}>
            {MODALITIES.map((m) => <MenuItem key={m.value} value={m.value}>{m.label}</MenuItem>)}
          </TextField>
          <Button
            variant="outlined"
            startIcon={draft.isPending ? <CircularProgress size={16} /> : <AutoAwesomeOutlined />}
            onClick={() => draft.mutate()}
            disabled={draft.isPending}
          >
            Draft
          </Button>
        </Stack>
      }
    >
      {draft.isError && <Alert severity="info" sx={{ mb: 2 }}>{getErrorMessage(draft.error)}</Alert>}
      {plans.data && !current && (
        <Typography color="text.secondary">
          No plan yet. Draft one from the record: goals, measurable objectives and interventions, each linked to evidence.
        </Typography>
      )}
      {current && (
        <Stack spacing={2}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Chip
              size="small"
              color={current.status === "active" ? "primary" : "default"}
              icon={current.status === "active" ? <Verified /> : undefined}
              label={current.status === "active" ? `Active since ${formatDate(current.signed_at)}` : "Draft: review before signing"}
            />
            <Chip size="small" variant="outlined" label={MODALITIES.find((m) => m.value === current.modality)?.label} />
            {current.ai_generated && <Chip size="small" variant="outlined" label="AI draft" />}
          </Stack>
          {current.problem_summary && (
            <Typography color="text.secondary">{current.problem_summary.replace(/\[S\d+\]/g, "")}</Typography>
          )}
          {current.goals.map((goal, i) => (
            <Box key={i}>
              <Typography fontWeight={600}>
                Goal {i + 1}: {goal.text}
                <CitationChips labels={goal.evidence.map((e) => e.label)} sources={goal.evidence} clientId={clientId} />
              </Typography>
              <Box component="ul" sx={{ pl: 2.5, my: 0.5 }}>
                {goal.objectives.map((o) => (
                  <li key={o.text}>
                    <Typography variant="body2">
                      {o.text}
                      {o.measure && <Typography component="span" variant="body2" color="text.secondary"> · measured by {o.measure}</Typography>}
                    </Typography>
                    {o.interventions.length > 0 && (
                      <Typography variant="caption" color="text.secondary">Interventions: {o.interventions.join("; ")}</Typography>
                    )}
                  </li>
                ))}
              </Box>
            </Box>
          ))}
          {current.status === "draft" && (
            <Box>
              <Button variant="contained" onClick={() => sign.mutate(current.id)} disabled={sign.isPending}>
                Sign as active plan
              </Button>
            </Box>
          )}
        </Stack>
      )}
    </Panel>
  );
};
