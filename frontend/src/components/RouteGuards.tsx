import { useState } from "react";
import { Alert, Box, Button, CircularProgress, Paper, Stack, Typography } from "@mui/material";
import { MarkEmailUnreadOutlined } from "@mui/icons-material";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, useRouterState } from "@tanstack/react-router";
import api, { getErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { RouterLink } from "./RouterLink";

const FullPageSpinner = () => (
  <Box sx={{ flex: 1, display: "grid", placeItems: "center", py: 10 }}>
    <CircularProgress />
  </Box>
);

const VerifyEmailNotice = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [sent, setSent] = useState<string | null>(null);
  const resend = useMutation({
    mutationFn: async () => (await api.post<{ detail: string }>("verify-email/resend/")).data,
    onSuccess: (data) => setSent(data.detail),
  });

  return (
    <Box sx={{ flex: 1, display: "grid", placeItems: "center", px: 2, py: 6 }}>
      <Paper variant="outlined" sx={{ p: { xs: 3, sm: 5 }, maxWidth: 480, borderRadius: 4, textAlign: "center" }}>
        <MarkEmailUnreadOutlined color="primary" sx={{ fontSize: 48 }} />
        <Typography variant="h5" component="h1" mt={1} gutterBottom>
          Confirm your email
        </Typography>
        <Typography color="text.secondary">
          We sent a link to <strong>{user?.email}</strong>. Click it to start using TherapyBot. Wrong address? Update it
          in your <RouterLink to="/profile">profile</RouterLink>.
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} justifyContent="center" mt={3}>
          <Button variant="contained" onClick={() => queryClient.invalidateQueries({ queryKey: ["current_user"] })}>
            I've verified it
          </Button>
          <Button variant="outlined" onClick={() => resend.mutate()} disabled={resend.isPending}>
            Resend link
          </Button>
        </Stack>
        {sent && (
          <Alert severity="success" sx={{ mt: 3 }}>
            {sent}
          </Alert>
        )}
        {resend.isError && (
          <Alert severity="error" sx={{ mt: 3 }}>
            {getErrorMessage(resend.error)}
          </Alert>
        )}
        <Typography variant="body2" color="text.secondary" mt={3}>
          Need support right now? Call or text <a href="tel:988">988</a> any time.
        </Typography>
      </Paper>
    </Box>
  );
};

/** Requires sign-in; with `verified`, also requires a confirmed email address. */
export const RequireAuth = ({ children, verified = false }: { children: React.ReactNode; verified?: boolean }) => {
  const { authenticated, loading, user } = useAuth();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  if (loading) return <FullPageSpinner />;
  if (!authenticated) return <Navigate to="/login" search={{ redirect: pathname }} replace />;
  if (verified && user && !user.email_verified) return <VerifyEmailNotice />;
  return <>{children}</>;
};

/** Therapist area: signed in, email verified, therapist role, and NPI verified (or a clear status if not). */
export const RequireTherapist = ({ children }: { children: React.ReactNode }) => {
  const { user } = useAuth();
  return (
    <RequireAuth verified>
      {user && user.role !== "therapist" ? (
        <Navigate to="/" replace />
      ) : user && user.npi_status !== "verified" ? (
        <Box sx={{ flex: 1, display: "grid", placeItems: "center", px: 2, py: 6 }}>
          <Paper variant="outlined" sx={{ p: { xs: 3, sm: 5 }, maxWidth: 520, borderRadius: 4, textAlign: "center" }}>
            <Typography variant="h5" component="h1" gutterBottom>
              {user.npi_status === "rejected" ? "We couldn't verify your NPI" : "We're verifying your NPI"}
            </Typography>
            <Typography color="text.secondary">
              {user.npi_status === "rejected"
                ? "Contact support and we'll help sort it out."
                : "We couldn't match it automatically with the NPI Registry, so a person is reviewing it. You'll be able to add clients as soon as it's approved, usually within one business day."}
            </Typography>
          </Paper>
        </Box>
      ) : (
        children
      )}
    </RequireAuth>
  );
};

/** Sends signed-in users onward, to `?redirect=` when present (set by RequireAuth). */
export const RequireGuest = ({ children }: { children: React.ReactNode }) => {
  const { authenticated, loading } = useAuth();
  const redirect = useRouterState({
    select: (s) => (s.location.search as { redirect?: string }).redirect,
  });

  if (loading) return <FullPageSpinner />;
  if (authenticated) return <Navigate to={redirect ?? "/"} replace />;
  return <>{children}</>;
};
