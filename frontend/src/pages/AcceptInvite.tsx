import { useState } from "react";
import { Alert, Box, Button, CircularProgress, FormControlLabel, Paper, Stack, Switch, Typography } from "@mui/material";
import { ShieldOutlined } from "@mui/icons-material";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import api, { getErrorMessage } from "../api/client";
import type { InvitePreview } from "../api/types";
import { AuthLayout } from "../components/AuthLayout";
import { LinkButton } from "../components/RouterLink";
import { useAuth } from "../context/AuthContext";

const SCOPES = [
  { key: "share_checkins", label: "Plan progress", help: "Which homework and plan steps you've done." },
  { key: "share_chat_summaries", label: "Summaries of your TherapyBot chats", help: "Short summaries, not the conversations themselves." },
  { key: "share_raw_chat", label: "Full chat conversations", help: "Everything you write to TherapyBot. Off unless you turn it on." },
] as const;

/** A client reviews exactly what a therapist will see, chooses what to share, and accepts. */
export const AcceptInvitePage = () => {
  const { t } = useSearch({ from: "/care-team/invite" });
  const { authenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const preview = useQuery({
    queryKey: ["invite", t],
    queryFn: async () => (await api.get<InvitePreview>("care-team/invite/", { params: { t } })).data,
    enabled: !!t,
    retry: false,
  });
  const [choices, setChoices] = useState<Record<string, boolean> | null>(null);
  const scopes = choices ?? preview.data?.defaults ?? {};
  const accept = useMutation({
    mutationFn: () => api.post("care-team/accept/", { t, ...scopes }),
    onSuccess: () => navigate({ to: "/profile" }),
  });
  const redirect = `/care-team/invite?t=${encodeURIComponent(t)}`;

  if (preview.isLoading) return <Box sx={{ display: "grid", placeItems: "center", py: 10 }}><CircularProgress /></Box>;
  if (!preview.data) {
    return (
      <AuthLayout title="Invitation">
        <Alert severity="warning">{getErrorMessage(preview.error, "This invitation link is incomplete.")}</Alert>
      </AuthLayout>
    );
  }
  const p = preview.data;
  const wrongAccount = authenticated && user && user.email.toLowerCase() !== p.invited_email.toLowerCase();

  return (
    <AuthLayout title={`${p.therapist_name} invited you`} subtitle={`${p.practice_name} uses TherapyBot between sessions.`}>
      <Stack spacing={2.5}>
        <Typography variant="body2">
          Connecting lets your therapist see what you choose below, so your time together can pick up where you are.
          You can change this or disconnect at any time.
        </Typography>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 3 }}>
          <Stack direction="row" spacing={1} alignItems="flex-start">
            <ShieldOutlined color="warning" fontSize="small" sx={{ mt: 0.25 }} />
            <Typography variant="body2"><strong>Always shared:</strong> {p.always_shared}</Typography>
          </Stack>
        </Paper>
        <Box>
          <Typography variant="subtitle2" gutterBottom>You choose</Typography>
          {SCOPES.map((s) => (
            <FormControlLabel
              key={s.key}
              sx={{ display: "flex", alignItems: "flex-start", mb: 1 }}
              control={<Switch checked={!!scopes[s.key]} onChange={(e) => setChoices({ ...scopes, [s.key]: e.target.checked })} />}
              label={<Box><Typography>{s.label}</Typography><Typography variant="caption" color="text.secondary">{s.help}</Typography></Box>}
            />
          ))}
        </Box>
        {!authenticated ? (
          <Stack spacing={1}>
            <Typography variant="body2" color="text.secondary">Sign in or create an account with {p.invited_email} to accept.</Typography>
            <Stack direction="row" spacing={1}>
              <LinkButton to="/login" search={{ redirect }} variant="contained">Sign in</LinkButton>
              <LinkButton to="/register" search={{ redirect }} variant="outlined">Create account</LinkButton>
            </Stack>
          </Stack>
        ) : wrongAccount ? (
          <Alert
            severity="warning"
            action={<Button color="inherit" size="small" onClick={() => logout()}>Sign out</Button>}
          >
            This invitation was sent to {p.invited_email}, but you're signed in as {user.email}. Sign out, then
            sign in or create an account with {p.invited_email} to accept it.
          </Alert>
        ) : (
          <Button variant="contained" size="large" onClick={() => accept.mutate()} disabled={accept.isPending}>
            Accept and connect
          </Button>
        )}
        {accept.isError && <Alert severity="error">{getErrorMessage(accept.error)}</Alert>}
      </Stack>
    </AuthLayout>
  );
};
