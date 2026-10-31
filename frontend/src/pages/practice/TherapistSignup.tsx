import { useState } from "react";
import { Alert, Box, Button, Checkbox, FormControlLabel, Stack, TextField, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import api, { getErrorMessage, getFieldErrors } from "../../api/client";
import { AuthLayout } from "../../components/AuthLayout";
import { RouterLink } from "../../components/RouterLink";
import { useAuth } from "../../context/AuthContext";

const FIELDS = ["first_name", "last_name", "email", "username", "password", "npi", "practice_name"] as const;
type Field = (typeof FIELDS)[number];

/** Therapist registration. The NPI is checked against the public NPI Registry before client access is granted. */
export const TherapistSignup = () => {
  const { login } = useAuth();
  const [form, setForm] = useState<Record<Field, string>>(
    Object.fromEntries(FIELDS.map((f) => [f, ""])) as Record<Field, string>,
  );
  const [agreed, setAgreed] = useState(false);
  const register = useMutation({
    mutationFn: async () => {
      await api.post("therapists/register/", { ...form, confirm_age: true, accept_terms: true });
      await login(form.username, form.password, true);
    },
  });
  const errors = getFieldErrors(register.error);
  const field = (name: Field, label: string, extra: object = {}) => (
    <TextField
      label={label}
      value={form[name]}
      onChange={(e) => setForm((f) => ({ ...f, [name]: e.target.value }))}
      error={!!errors[name]}
      helperText={errors[name]}
      {...extra}
    />
  );

  return (
    <AuthLayout
      title="TherapyBot for therapists"
      subtitle="Session prep, documentation drafts and progress tracking, grounded in your own clients' records."
      footer={<>Looking for support yourself? <RouterLink to="/register">Create a personal account</RouterLink></>}
    >
      <Box component="form" onSubmit={(e) => { e.preventDefault(); register.mutate(); }}>
        <Stack spacing={2}>
          {register.isError && !Object.keys(errors).length && <Alert severity="error">{getErrorMessage(register.error)}</Alert>}
          <Stack direction="row" spacing={2}>
            {field("first_name", "First name", { required: true, autoComplete: "given-name" })}
            {field("last_name", "Last name", { required: true, autoComplete: "family-name" })}
          </Stack>
          {field("email", "Work email", { type: "email", required: true, autoComplete: "email" })}
          {field("username", "Username", { required: true, autoComplete: "username" })}
          {field("password", "Password", { type: "password", required: true, autoComplete: "new-password" })}
          {field("npi", "NPI number", {
            required: true, inputProps: { inputMode: "numeric", maxLength: 10 },
            helperText: errors.npi ?? "We check it against the NPI Registry. Use your name as it appears there.",
          })}
          {field("practice_name", "Practice name (optional)")}
          <FormControlLabel
            control={<Checkbox checked={agreed} onChange={(e) => setAgreed(e.target.checked)} required />}
            label={<Typography variant="body2">I agree to the <RouterLink to="/terms">Terms</RouterLink> and <RouterLink to="/privacy">Privacy Policy</RouterLink>.</Typography>}
          />
          <Button type="submit" variant="contained" size="large" disabled={!agreed || register.isPending}>
            {register.isPending ? "Creating account…" : "Create therapist account"}
          </Button>
        </Stack>
      </Box>
    </AuthLayout>
  );
};
