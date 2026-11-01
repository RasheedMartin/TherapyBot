import { useState } from "react";
import { Alert, Box, Button, Checkbox, FormControlLabel, Stack, TextField } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { getErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { AuthLayout } from "./AuthLayout";
import { GoogleSignIn } from "./GoogleSignIn";
import { RouterLink } from "./RouterLink";
import { useReturnHere } from "./returnTo";

export const Login = () => {
  const returnHere = useReturnHere();
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);

  // RequireGuest handles the redirect once the user is authenticated
  const loginMutation = useMutation({
    mutationFn: () => login(username.trim(), password, rememberMe),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loginMutation.mutate();
  };

  const errorMessage =
    loginMutation.error instanceof AxiosError && loginMutation.error.response?.status === 401
      ? "Incorrect username or password."
      : getErrorMessage(loginMutation.error);

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue your conversations."
      footer={
        <>
          New here? <RouterLink to="/register" search={returnHere}>Create an account</RouterLink>
        </>
      }
    >
      <Box component="form" onSubmit={handleSubmit}>
        <Stack spacing={2.5}>
          {loginMutation.isError && <Alert severity="error">{errorMessage}</Alert>}
          <TextField
            label="Username"
            name="username"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <TextField
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <FormControlLabel
              control={<Checkbox checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} />}
              label="Remember me"
            />
            <RouterLink to="/forgot-password" variant="body2">
              Forgot password?
            </RouterLink>
          </Stack>
          <Button type="submit" variant="contained" size="large" disabled={loginMutation.isPending}>
            {loginMutation.isPending ? "Signing in…" : "Sign in"}
          </Button>
        </Stack>
      </Box>
      <GoogleSignIn />
    </AuthLayout>
  );
};
