import { useState } from "react";
import { Alert, Box, Button, Stack, TextField } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import api, { getErrorMessage } from "../api/client";
import { AuthLayout } from "./AuthLayout";
import { RouterLink } from "./RouterLink";

export const ForgotPasswordPage = () => {
  const [email, setEmail] = useState("");

  const forgotPasswordMutation = useMutation({
    mutationFn: (data: { email: string }) => api.post("forgot-password/", data),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    forgotPasswordMutation.mutate({ email: email.trim() });
  };

  return (
    <AuthLayout
      title="Reset your password"
      subtitle="Enter the email on your account and we'll send you a reset link."
      footer={<RouterLink to="/login">Back to sign in</RouterLink>}
    >
      {forgotPasswordMutation.isSuccess ? (
        <Alert severity="success">
          If an account exists for <strong>{email}</strong>, a reset link is on its way. Check your inbox (and spam
          folder).
        </Alert>
      ) : (
        <Box component="form" onSubmit={handleSubmit}>
          <Stack spacing={2.5}>
            {forgotPasswordMutation.isError && (
              <Alert severity="error">{getErrorMessage(forgotPasswordMutation.error)}</Alert>
            )}
            <TextField
              type="email"
              label="Email"
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Button type="submit" variant="contained" size="large" disabled={forgotPasswordMutation.isPending}>
              {forgotPasswordMutation.isPending ? "Sending…" : "Send reset link"}
            </Button>
          </Stack>
        </Box>
      )}
    </AuthLayout>
  );
};
