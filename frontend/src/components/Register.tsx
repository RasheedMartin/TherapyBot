import { useState } from "react";
import {
  Box,
  Paper,
  Stack,
  TextField,
  Button,
  Typography,
  Link,
} from "@mui/material";
import { useNavigate } from "@tanstack/react-router";
import api from "../api/client";
import { useMutation } from "@tanstack/react-query";
import type { AxiosResponse } from "axios";

interface RegisterFormData {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export const RegisterPage = () => {
  const navigate = useNavigate();

  const [formData, setFormData] = useState<RegisterFormData>({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });

  // Mutation for registering a user
  const registerMutation = useMutation<
    AxiosResponse<any>,
    Error,
    Omit<RegisterFormData, "confirmPassword">
  >({
    mutationFn: (data) => api.post("register_user/", data),
    onSuccess: () => {
      navigate({ to: "/login" });
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (formData.password !== formData.confirmPassword) {
      alert("Passwords do not match");
      return;
    }
    registerMutation.mutate({
      username: formData.username,
      email: formData.email,
      password: formData.password,
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
        p: 2,
      }}
    >
      <Paper
        elevation={6}
        sx={{ p: 5, borderRadius: 3, width: "100%", maxWidth: 400 }}
      >
        <Typography variant="h4" component="h1" gutterBottom textAlign="center">
          Register
        </Typography>
        <Typography
          variant="body2"
          color="textSecondary"
          gutterBottom
          textAlign="center"
        >
          Create a new account to start using TherapyBot
        </Typography>

        <Box component="form" onSubmit={() => handleSubmit}>
          <Stack spacing={3} mt={2}>
            <TextField
              name="username"
              label="Username"
              variant="outlined"
              value={formData.username}
              onChange={handleChange}
              required
              fullWidth
            />
            <TextField
              name="email"
              label="Email"
              variant="outlined"
              value={formData.email}
              onChange={handleChange}
              required
              fullWidth
            />
            <TextField
              name="password"
              label="Password"
              type="password"
              variant="outlined"
              value={formData.password}
              onChange={handleChange}
              required
              fullWidth
            />
            <TextField
              name="confirmPassword"
              label="Confirm Password"
              type="password"
              variant="outlined"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
              fullWidth
            />

            {registerMutation.isError && (
              <Typography variant="body2" color="error" textAlign="center">
                {registerMutation.error.message}
              </Typography>
            )}

            <Button
              type="submit"
              variant="contained"
              color="primary"
              fullWidth
              sx={{ py: 1.5 }}
              disabled={registerMutation.isPending}
            >
              {registerMutation.isPending ? "Registering..." : "Register"}
            </Button>

            <Typography variant="body2" textAlign="center">
              Already have an account?{" "}
              <Link
                component="button"
                variant="body2"
                onClick={() => navigate({ to: "/login" })}
              >
                Back to login
              </Link>
            </Typography>
          </Stack>
        </Box>
      </Paper>
    </Box>
  );
};
