import { useState } from "react";
import { Alert, Box, Button, Stack, TextField } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import api, { getErrorMessage, getFieldErrors } from "../api/client";
import { useSearch } from "@tanstack/react-router";
import { AuthLayout } from "./AuthLayout";
import { RouterLink } from "./RouterLink";

export const ResetPasswordPage = () => {
  const { uid, token } = useSearch({ from: "/reset-password" });
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mismatch, setMismatch] = useState(false);

  const resetPasswordMutation = useMutation({
    mutationFn: (data: { uid: string; token: string; new_password: string }) => api.post("reset-password/", data),
  });

  const fieldErrors = getFieldErrors(resetPasswordMutation.error);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setMismatch(true);
      return;
    }
    resetPasswordMutation.mutate({ uid, token, new_password: password });
  };

  if (!uid || !token) {
    return (
      <AuthLayout title="Invalid reset link" footer={<RouterLink to="/forgot-password">Request a new link</RouterLink>}>
        <Alert severity="warning">This password reset link is incomplete. Please use the link from your email.</Alert>
      </AuthLayout>
    );
  }

  if (resetPasswordMutation.isSuccess) {
    return (
      <AuthLayout title="Password updated">
        <Stack spacing={2.5}>
          <Alert severity="success">Your password has been reset. You can now sign in with it.</Alert>
          <Button component={RouterLink} to="/login" variant="contained" size="large">
            Sign in
          </Button>
        </Stack>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Choose a new password" footer={<RouterLink to="/login">Back to sign in</RouterLink>}>
      <Box component="form" onSubmit={handleSubmit}>
        <Stack spacing={2.5}>
          {resetPasswordMutation.isError && !fieldErrors.new_password && (
            <Alert severity="error">{getErrorMessage(resetPasswordMutation.error)}</Alert>
          )}
          <TextField
            type="password"
            label="New password"
            autoComplete="new-password"
            autoFocus
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setMismatch(false);
            }}
            error={!!fieldErrors.new_password}
            helperText={fieldErrors.new_password}
            required
          />
          <TextField
            type="password"
            label="Confirm new password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              setMismatch(false);
            }}
            error={mismatch}
            helperText={mismatch ? "Passwords don't match." : undefined}
            required
          />
          <Button type="submit" variant="contained" size="large" disabled={resetPasswordMutation.isPending}>
            {resetPasswordMutation.isPending ? "Saving…" : "Reset password"}
          </Button>
        </Stack>
      </Box>
    </AuthLayout>
  );
};
