import { useState } from "react";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  List,
  ListItemAvatar,
  ListItemButton,
  ListItemText,
  Paper,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { PersonAddAlt1, WarningAmberRounded } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import api, { getErrorMessage, getFieldErrors } from "../../api/client";
import type { PracticeClient, RiskFlag } from "../../api/types";
import { formatDate } from "../../components/practice/format";
import { SyntheticDataBanner } from "../../components/practice/SyntheticDataBanner";
import { useAuth } from "../../context/AuthContext";

const InviteClientDialog = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const invite = useMutation({
    mutationFn: () => api.post("practice/clients/", { display_name: name.trim(), email: email.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["practice-clients"] });
      setName("");
      setEmail("");
      onClose();
    },
  });
  const errors = getFieldErrors(invite.error);
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <Box component="form" onSubmit={(e) => { e.preventDefault(); invite.mutate(); }}>
        <DialogTitle>Invite a client</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" mb={2}>
            They'll get an email to connect with you. Before accepting, they'll see exactly what you'll be able to see,
            and they choose what to share between sessions.
          </Typography>
          <Stack spacing={2}>
            <TextField label="Client name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
            <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                       error={!!errors.email} helperText={errors.email} />
          </Stack>
          {invite.isError && !errors.email && <Alert severity="error" sx={{ mt: 2 }}>{getErrorMessage(invite.error)}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={invite.isPending || !name.trim() || !email.trim()}>
            Send invitation
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};

const RiskFlagInbox = () => {
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
            <strong>{flag.client_name}</strong> · {flag.reason}
            <Typography variant="caption" display="block">{new Date(flag.created_at).toLocaleString()}</Typography>
          </Alert>
        ))}
      </Stack>
    </Paper>
  );
};

export const PracticeHome = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [inviting, setInviting] = useState(false);
  const clients = useQuery({
    queryKey: ["practice-clients"],
    queryFn: async () => (await api.get<PracticeClient[]>("practice/clients/")).data,
  });

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3} spacing={2}>
        <Box>
          <Typography variant="h4" component="h1">
            Your clients
          </Typography>
          <Typography color="text.secondary">Welcome back, {user?.display_name}.</Typography>
        </Box>
        <Button variant="contained" startIcon={<PersonAddAlt1 />} onClick={() => setInviting(true)} sx={{ flexShrink: 0 }}>
          Invite client
        </Button>
      </Stack>
      <Stack spacing={3}>
        <SyntheticDataBanner />
        <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "3fr 2fr" }, alignItems: "start" }}>
          <Paper variant="outlined" sx={{ borderRadius: 4, overflow: "hidden" }}>
            {clients.isLoading && <Box p={2}><Skeleton height={56} /><Skeleton height={56} /></Box>}
            {clients.isError && <Alert severity="error">{getErrorMessage(clients.error)}</Alert>}
            {clients.data?.length === 0 && (
              <Box p={4} textAlign="center">
                <Typography variant="h6" gutterBottom>No clients yet</Typography>
                <Typography color="text.secondary" mb={2}>Invite a client to start building their record.</Typography>
                <Button variant="outlined" onClick={() => setInviting(true)}>Invite your first client</Button>
              </Box>
            )}
            <List disablePadding>
              {clients.data?.map((c) => (
                <ListItemButton
                  key={c.id}
                  divider
                  onClick={() => navigate({ to: "/practice/clients/$clientId", params: { clientId: String(c.id) } })}
                  sx={{ py: 1.5 }}
                >
                  <ListItemAvatar>
                    <Avatar sx={{ bgcolor: "primary.main" }}>{c.display_name[0]}</Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={c.display_name}
                    secondary={
                      c.relationship?.status === "invited"
                        ? `Invited ${formatDate(c.relationship.invited_at)}`
                        : `Connected ${formatDate(c.relationship?.consented_at ?? null)}`
                    }
                    slotProps={{ primary: { fontWeight: 600 } }}
                  />
                  <Chip size="small" label={c.relationship?.status === "invited" ? "Invite pending" : "Active"}
                        color={c.relationship?.status === "invited" ? "default" : "primary"} variant="outlined" />
                </ListItemButton>
              ))}
            </List>
          </Paper>
          <RiskFlagInbox />
        </Box>
      </Stack>
      <InviteClientDialog open={inviting} onClose={() => setInviting(false)} />
    </Container>
  );
};
