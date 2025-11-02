// src/pages/ForgotPasswordPage.tsx
import { useState } from "react";
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Stack,
  Link,
} from "@mui/material";
import { useNavigate } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import api from "../api/client";

export const ForgotPasswordPage = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");

  const forgotPasswordMutation = useMutation({
    mutationFn: (data: { email: string }) => api.post("forgot-password/", data),
    onSuccess: () => {
      alert("Password reset email sent! Please check your inbox.");
      navigate({ to: "/login" });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    forgotPasswordMutation.mutate({ email });
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
          Forgot Password
        </Typography>
        <Typography
          variant="body2"
          textAlign="center"
          color="textSecondary"
          mb={2}
        >
          Enter your email to receive password reset instructions.
        </Typography>

        <Box component="form" onSubmit={handleSubmit}>
          <Stack spacing={2}>
            <TextField
              type="email"
              label="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              fullWidth
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={forgotPasswordMutation.isPending}
            >
              {forgotPasswordMutation.isPending
                ? "Sending..."
                : "Send Reset Link"}
            </Button>
          </Stack>
        </Box>

        <Typography variant="body2" textAlign="center" mt={3}>
          <Link component="button" onClick={() => navigate({ to: "/login" })}>
            Back to Login
          </Link>
        </Typography>
      </Paper>
    </Box>
  );
};
