import {
  Box,
  Paper,
  Stack,
  TextField,
  Button,
  FormControlLabel,
  Typography,
  Checkbox,
} from "@mui/material";

import { useState } from "react";
import api from "../api/client";
import { useMutation } from "@tanstack/react-query";
import { useNavigate, Link, useRouter } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";
import { useUser } from "../context/UserContext";

export const Login = () => {
  const navigate = useNavigate();
  const { authenticated, login, logout } = useAuth();
  const { refetch } = useUser();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loginMutation.mutate({
      username,
      password,
    });
  };

  const loginMutation = useMutation({
    mutationFn: (data: { username: string; password: string }) =>
      api.post("/token/", data),
    onSuccess: (response) => {
      const token = response.data.token;
      if (rememberMe) {
        localStorage.setItem("authToken", token);
      } else {
        sessionStorage.setItem("authToken", token);
      }
      const { access, refresh } = response.data;
      login(access, refresh);
      refetch();
      navigate({ to: "/get-started" });
    },
    onError: () => logout(),
  });

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: "#f5f5f5",
        p: 2,
      }}
    >
      {!authenticated && (
        <Paper
          elevation={6}
          sx={{
            p: 5,
            borderRadius: 3,
            width: "100%",
            maxWidth: 400,
          }}
        >
          {/* Heading */}
          <Typography
            variant="h4"
            component="h1"
            gutterBottom
            textAlign="center"
          >
            Login
          </Typography>
          <Typography
            variant="body2"
            color="textSecondary"
            gutterBottom
            textAlign="center"
          >
            Welcome back! Please enter your credentials to continue.
          </Typography>

          {/* Login Form */}
          <Stack spacing={3} mt={2}>
            <TextField
              type="text"
              placeholder="Enter Username"
              name="username"
              variant="outlined"
              value={username}
              required
              fullWidth
              onChange={(e) => setUsername(e.target.value)}
            />
            <TextField
              type="password"
              placeholder="Enter Password"
              name="password"
              variant="outlined"
              value={password}
              required
              fullWidth
              onChange={(e) => setPassword(e.target.value)}
            />

            <FormControlLabel
              control={
                <Checkbox
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                />
              }
              label="Remember me"
            />
            <Button
              type="submit"
              variant="contained"
              color="primary"
              fullWidth
              onClick={handleSubmit}
              sx={{ py: 1.5 }}
            >
              {loginMutation.isPending ? "Logging In..." : "Login"}
            </Button>

            {loginMutation.isError && (
              <Typography variant="body2" color="error" textAlign="center">
                {loginMutation.error.message}
              </Typography>
            )}

            {/* Actions */}
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                mt: 1,
              }}
            >
              <Button variant="outlined" onClick={() => router.history.back()}>
                Cancel
              </Button>
              <Link to="/forgot-password">Forgot password?</Link>
            </Box>
          </Stack>
        </Paper>
      )}

      {/* Navigation Buttons */}
      <Stack direction="row" spacing={2} mt={4} justifyContent="center">
        <Button variant="text" onClick={() => navigate({ to: "/" })}>
          Back to Home
        </Button>
        <Button variant="text" onClick={() => navigate({ to: "/register" })}>
          Register
        </Button>
      </Stack>
    </Box>
  );
};
