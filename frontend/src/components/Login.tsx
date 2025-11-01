import { CheckBox } from "@mui/icons-material";
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

import { useEffect, useState } from "react";
import api from "../api/client";
import { useQuery } from "@tanstack/react-query";
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
  const getLogin = async () => {
    return await api.post("/token/", {
      username: username,
      password: password,
    });
  };

  const {
    data: loginData,
    error,
    isLoading,
    refetch: loginUser,
  } = useQuery({
    queryKey: ["login"],
    queryFn: getLogin,
    retry: false,
    enabled: false,
  });

  useEffect(() => {
    if (loginData) {
      const { access, refresh } = loginData.data;
      login(access, refresh);
      refetch();
      navigate({ to: "/get-started" });
    }
    if (error) {
      logout();
    }
  }, [loginData, error]);

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

            <FormControlLabel control={<Checkbox />} label="Remember me" />

            <Button
              type="submit"
              variant="contained"
              color="primary"
              fullWidth
              onClick={loginUser}
              sx={{ py: 1.5 }}
            >
              {isLoading ? "Logging In..." : "Login"}
            </Button>

            {error && (
              <Typography variant="body2" color="error" textAlign="center">
                {error.message}
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
              <Link href="/forgot-password" underline="hover" variant="body2">
                Forgot password?
              </Link>
            </Box>
          </Stack>
        </Paper>
      )}

      {/* Navigation Buttons */}
      <Stack direction="row" spacing={2} mt={4} justifyContent="center">
        <Button variant="text" onClick={() => navigate({ to: "/" })}>
          Back to Home
        </Button>
        <Button
          variant="text"
          onClick={() => navigate({ to: "/reset_password" })}
        >
          Reset Password
        </Button>
        <Button variant="text" onClick={() => navigate({ to: "/register" })}>
          Register
        </Button>
      </Stack>
    </Box>
  );
};
