import { useEffect, useRef } from "react";
import { Alert, Button, CircularProgress, Stack } from "@mui/material";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useSearch } from "@tanstack/react-router";
import api, { getErrorMessage } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { useAuth } from "../context/AuthContext";

/** Landing page for the link in the verification email. */
export const VerifyEmailPage = () => {
  const { uid, token } = useSearch({ from: "/verify-email" });
  const { authenticated } = useAuth();
  const queryClient = useQueryClient();

  const verify = useMutation({
    mutationFn: () => api.post("verify-email/", { uid, token }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["current_user"] }),
  });

  // Tokens are single-use, so submit exactly once (StrictMode runs effects twice in development)
  const submitted = useRef(false);
  useEffect(() => {
    if (uid && token && !submitted.current) {
      submitted.current = true;
      verify.mutate();
    }
  }, [uid, token, verify]);

  return (
    <AuthLayout title="Email verification">
      <Stack spacing={2.5} alignItems="stretch">
        {(verify.isPending || verify.isIdle) && uid && token && <CircularProgress sx={{ alignSelf: "center" }} />}
        {(!uid || !token) && <Alert severity="warning">This link is incomplete. Please use the link from your email.</Alert>}
        {verify.isSuccess && <Alert severity="success">Your email is confirmed. You're all set.</Alert>}
        {verify.isError && <Alert severity="error">{getErrorMessage(verify.error)}</Alert>}
        {!verify.isPending && (
          <Button component={Link} to={authenticated ? "/chat" : "/login"} variant="contained" size="large">
            {authenticated ? "Start chatting" : "Sign in"}
          </Button>
        )}
      </Stack>
    </AuthLayout>
  );
};
