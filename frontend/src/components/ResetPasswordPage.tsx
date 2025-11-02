// src/pages/ResetPasswordPage.tsx
import { useState } from "react";
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Stack,
} from "@mui/material";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import api from "../api/client";

export const ResetPasswordPage = () => {
  const navigate = useNavigate();
  const search = useSearch({ from: "/reset-password" }); // if you include ?token=
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const resetPasswordMutation = useMutation({
    mutationFn: (data: { uid: string; token: string; new_password: string }) =>
      api.post("/reset-password/", data),
    onSuccess: () => {
      alert("Password reset successful!");
      navigate({ to: "/login" });
    },
    onError: () => {
      alert("Failed to reset password. Please try again.");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      alert("Passwords do not match!");
      return;
    }

    if (!search.token) {
      alert("Invalid or missing token!");
      return;
    }

    resetPasswordMutation.mutate({
      uid: search.uid,
      token: search.token,
      new_password: password,
    });
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: "#f5f5f5",
      }}
    >
      <Paper
        elevation={6}
        sx={{ p: 4, borderRadius: 3, width: "100%", maxWidth: 400 }}
      >
        <Typography variant="h4" textAlign="center" gutterBottom>
          Reset Password
        </Typography>

        <Box component="form" onSubmit={handleSubmit}>
          <Stack spacing={2}>
            <TextField
              type="password"
              label="New Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              fullWidth
            />
            <TextField
              type="password"
              label="Confirm New Password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              fullWidth
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={resetPasswordMutation.isPending}
            >
              {resetPasswordMutation.isPending
                ? "Resetting..."
                : "Reset Password"}
            </Button>
          </Stack>
        </Box>
      </Paper>
    </Box>
  );
};
