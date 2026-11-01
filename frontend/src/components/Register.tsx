import { useState } from "react";
import { Alert, Box, Button, Checkbox, FormControlLabel, FormHelperText, Stack, TextField } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import api, { getErrorMessage, getFieldErrors } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { AuthLayout } from "./AuthLayout";
import { GoogleSignIn } from "./GoogleSignIn";
import { RouterLink } from "./RouterLink";
import { useReturnHere } from "./returnTo";

interface RegisterFormData {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export const RegisterPage = () => {
  const returnHere = useReturnHere();
  const { login } = useAuth();
  const [formData, setFormData] = useState<RegisterFormData>({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [mismatch, setMismatch] = useState(false);
  const [agreed, setAgreed] = useState(false);

  // Sign the new user straight in; RequireGuest then redirects to the chat
  const registerMutation = useMutation({
    mutationFn: async ({ username, email, password }: Omit<RegisterFormData, "confirmPassword">) => {
      await api.post("register/", { username, email, password, confirm_age: true, accept_terms: true });
      await login(username, password, true);
    },
  });

  const fieldErrors = getFieldErrors(registerMutation.error);
  const hasFieldErrors = Object.keys(fieldErrors).length > 0;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (name === "password" || name === "confirmPassword") setMismatch(false);
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (formData.password !== formData.confirmPassword) {
      setMismatch(true);
      return;
    }
    registerMutation.mutate({
      username: formData.username.trim(),
      email: formData.email.trim(),
      password: formData.password,
    });
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Your conversations are saved privately to your account."
      footer={
        <>
          Already have an account? <RouterLink to="/login" search={returnHere}>Sign in</RouterLink>
        </>
      }
    >
      <Box component="form" onSubmit={handleSubmit}>
        <Stack spacing={2.5}>
          {registerMutation.isError && !hasFieldErrors && (
            <Alert severity="error">{getErrorMessage(registerMutation.error)}</Alert>
          )}
          <TextField
            name="username"
            label="Username"
            autoComplete="username"
            autoFocus
            value={formData.username}
            onChange={handleChange}
            error={!!fieldErrors.username}
            helperText={fieldErrors.username}
            required
          />
          <TextField
            name="email"
            label="Email"
            type="email"
            autoComplete="email"
            value={formData.email}
            onChange={handleChange}
            error={!!fieldErrors.email}
            helperText={fieldErrors.email ?? "Used only for password resets."}
            required
          />
          <TextField
            name="password"
            label="Password"
            type="password"
            autoComplete="new-password"
            value={formData.password}
            onChange={handleChange}
            error={!!fieldErrors.password}
            helperText={fieldErrors.password ?? "At least 8 characters, not too common."}
            required
          />
          <TextField
            name="confirmPassword"
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            value={formData.confirmPassword}
            onChange={handleChange}
            error={mismatch}
            helperText={mismatch ? "Passwords don't match." : undefined}
            required
          />
          <Box>
            <FormControlLabel
              control={<Checkbox checked={agreed} onChange={(e) => setAgreed(e.target.checked)} required />}
              label={
                <>
                  I'm 18 or older and agree to the <RouterLink to="/terms">Terms</RouterLink> and{" "}
                  <RouterLink to="/privacy">Privacy Policy</RouterLink>.
                </>
              }
              slotProps={{ typography: { variant: "body2" } }}
            />
            {(fieldErrors.confirm_age || fieldErrors.accept_terms) && (
              <FormHelperText error>{fieldErrors.confirm_age ?? fieldErrors.accept_terms}</FormHelperText>
            )}
          </Box>
          <Button type="submit" variant="contained" size="large" disabled={registerMutation.isPending || !agreed}>
            {registerMutation.isPending ? "Creating account…" : "Create account"}
          </Button>
        </Stack>
      </Box>
      <GoogleSignIn />
    </AuthLayout>
  );
};
