import {
  Alert,
  Button,
  Chip,
  Paper,
  Skeleton,
  Stack,
  Typography,
} from "@mui/material";
import { WarningAmberRounded } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import api from "../../api/client";
import type { RiskFlag } from "../../api/types";

/** Open safety flags for clients in this therapist's care, with a way to open the record and acknowledge. */
export const RiskFlagInbox = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const flags = useQuery({
    queryKey: ["risk-flags"],
    queryFn: async () => (await api.get<RiskFlag[]>("practice/risk-flags/")).data,
  });
  const acknowledge = useMutation({
    mutationFn: (id: number) => api.post(`practice/risk-flags/${id}/acknowledge/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["risk-flags"] }),
  });
  const open = flags.data?.filter((f) => !f.acknowledged_at) ?? [];
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4, borderColor: open.length ? "warning.main" : "divider" }}>
      <Stack direction="row" spacing={1} alignItems="center" mb={1}>
        <WarningAmberRounded color={open.length ? "warning" : "disabled"} />
        <Typography variant="h6" component="h2">
          Safety flags
        </Typography>
        {!!open.length && <Chip size="small" color="warning" label={open.length} />}
      </Stack>
      <Typography variant="body2" color="text.secondary" mb={2}>
        Raised by screenings and between-session check-ins. Clients are told these aren't monitored in real time.
      </Typography>
      {flags.isLoading && <Skeleton height={48} />}
      {flags.data && open.length === 0 && <Typography color="text.secondary">No open flags.</Typography>}
      <Stack spacing={1.5}>
        {open.map((flag) => (
          <Alert
            key={flag.id}
            severity={flag.level === "imminent" ? "error" : "warning"}
            action={
              <Stack direction="row" spacing={1}>
                <Button size="small" color="inherit" onClick={() => navigate({ to: "/practice/clients/$clientId", params: { clientId: String(flag.client_id) } })}>
                  Open
                </Button>
                <Button size="small" color="inherit" onClick={() => acknowledge.mutate(flag.id)}>
                  Acknowledge
                </Button>
              </Stack>
            }
          >
            <strong>{flag.client_name}</strong>: {flag.reason}
            <Typography variant="caption" display="block">{new Date(flag.created_at).toLocaleString()}</Typography>
          </Alert>
        ))}
      </Stack>
    </Paper>
  );
};
