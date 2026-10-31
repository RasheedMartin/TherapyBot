import { useEffect, useState } from "react";
import {
  Alert,
  Avatar,
  Box,
  Button,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  MenuItem,
  Paper,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { DeleteForeverOutlined, DownloadOutlined } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import api, { getErrorMessage, getFieldErrors } from "../api/client";
import type { Profile, SessionFormat } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { ReminderSettings } from "../components/plans/ReminderSettings";

type ProfileForm = Omit<Profile, "username" | "date_joined">;

const SESSION_FORMATS: { value: SessionFormat; label: string }[] = [
  { value: "any", label: "No preference" },
  { value: "in_person", label: "In person" },
  { value: "telehealth", label: "Telehealth" },
];

const Section = ({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) => (
  <Paper variant="outlined" sx={{ p: { xs: 2.5, sm: 4 }, borderRadius: 4 }}>
    <Typography variant="h6" component="h2">
      {title}
    </Typography>
    {description && (
      <Typography variant="body2" color="text.secondary" mt={0.5}>
        {description}
      </Typography>
    )}
    <Box mt={3}>{children}</Box>
  </Paper>
);

const ProfileDetails = ({ profile, onSaved }: { profile: Profile; onSaved: () => void }) => {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ProfileForm>(profile);

  useEffect(() => setForm(profile), [profile]);

  const save = useMutation({
    mutationFn: async (data: ProfileForm) => (await api.patch<Profile>("profile/", data)).data,
    onSuccess: (data) => {
      queryClient.setQueryData(["profile"], data);
      queryClient.invalidateQueries({ queryKey: ["current_user"] });
      onSaved();
    },
  });
  const errors = getFieldErrors(save.error);
  const dirty = (Object.keys(form) as (keyof ProfileForm)[]).some((k) => form[k] !== profile[k]);

  const field = (name: keyof ProfileForm) => ({
    name,
    value: form[name],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [name]: e.target.value })),
    error: !!errors[name],
  });

  return (
    <Box
      component="form"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(form);
      }}
    >
      <Stack spacing={3}>
        <Section title="About you" description="TherapyBot uses this to make conversations feel more personal.">
          <Stack spacing={2.5}>
            <TextField {...field("display_name")} label="What should we call you?" placeholder={profile.username} helperText={errors.display_name} />
            <TextField {...field("email")} label="Email" type="email" helperText={errors.email ?? "Used for password resets."} />
            <TextField
              {...field("goals")}
              label="What would you like to work on?"
              placeholder="e.g. Feeling less anxious at work, sleeping better, fewer arguments at home"
              multiline
              minRows={3}
              helperText={errors.goals}
            />
          </Stack>
        </Section>

        <Section
          title="Care preferences"
          description="Optional. Used to find therapists and resources that fit you. Never shared without your permission."
        >
          <Stack spacing={2.5}>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2.5}>
              <TextField
                {...field("zip_code")}
                label="ZIP code"
                inputProps={{ inputMode: "numeric", maxLength: 5 }}
                helperText={errors.zip_code}
              />
              <TextField {...field("session_format")} select label="Session format">
                {SESSION_FORMATS.map((f) => (
                  <MenuItem key={f.value} value={f.value}>
                    {f.label}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
            <TextField
              {...field("insurance")}
              label="Insurance"
              placeholder="e.g. Aetna, Medicaid, or self-pay"
              helperText={errors.insurance}
            />
          </Stack>
        </Section>

        {save.isError && Object.keys(errors).length === 0 && <Alert severity="error">{getErrorMessage(save.error)}</Alert>}
        <Box display="flex" justifyContent="flex-end">
          <Button type="submit" variant="contained" size="large" disabled={!dirty || save.isPending}>
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
        </Box>
      </Stack>
    </Box>
  );
};

const ChangePassword = ({ hasPassword, onSaved }: { hasPassword: boolean; onSaved: () => void }) => {
  const queryClient = useQueryClient();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const change = useMutation({
    mutationFn: () => api.post("account/password/", { current_password: current, new_password: next }),
    onSuccess: () => {
      setCurrent("");
      setNext("");
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      onSaved();
    },
  });
  const errors = getFieldErrors(change.error);

  return (
    <Section
      title="Password"
      description={hasPassword ? undefined : "You sign in with Google. Set a password if you'd also like to sign in with your username."}
    >
      <Box
        component="form"
        onSubmit={(e) => {
          e.preventDefault();
          change.mutate();
        }}
      >
        <Stack spacing={2.5}>
          {hasPassword && (
            <TextField
              label="Current password"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              error={!!errors.current_password}
              helperText={errors.current_password}
              required
            />
          )}
          <TextField
            label="New password"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            error={!!errors.new_password}
            helperText={errors.new_password}
            required
          />
          <Box display="flex" justifyContent="flex-end">
            <Button type="submit" variant="outlined" disabled={change.isPending || (hasPassword && !current) || !next}>
              {hasPassword ? "Update password" : "Set password"}
            </Button>
          </Box>
        </Stack>
      </Box>
    </Section>
  );
};

const PrivacyAndData = ({ hasPassword }: { hasPassword: boolean }) => {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [password, setPassword] = useState("");

  const exportData = useMutation({
    mutationFn: async () => {
      const res = await api.get("account/export/", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = "therapybot-data.json";
      link.click();
      URL.revokeObjectURL(url);
    },
  });

  const deleteAccount = useMutation({
    mutationFn: () => api.post("account/delete/", hasPassword ? { password } : { confirm: password }),
    onSuccess: async () => {
      setConfirmOpen(false);
      await logout();
      navigate({ to: "/" });
    },
  });
  const deleteErrors = getFieldErrors(deleteAccount.error);

  return (
    <Section title="Privacy & data" description="Your conversations are private to your account. You're in control of your data.">
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <Button
          variant="outlined"
          startIcon={<DownloadOutlined />}
          onClick={() => exportData.mutate()}
          disabled={exportData.isPending}
        >
          {exportData.isPending ? "Preparing…" : "Download my data"}
        </Button>
        <Button color="error" variant="outlined" startIcon={<DeleteForeverOutlined />} onClick={() => setConfirmOpen(true)}>
          Delete account
        </Button>
      </Stack>
      {exportData.isError && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {getErrorMessage(exportData.error)}
        </Alert>
      )}

      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)} maxWidth="xs" fullWidth>
        <Box
          component="form"
          onSubmit={(e) => {
            e.preventDefault();
            deleteAccount.mutate();
          }}
        >
          <DialogTitle>Delete your account?</DialogTitle>
          <DialogContent>
            <DialogContentText mb={2}>
              This permanently deletes your profile and every conversation. It can't be undone. You may want to
              download your data first.
            </DialogContentText>
            <TextField
              label={hasPassword ? "Enter your password to confirm" : "Type DELETE to confirm"}
              type={hasPassword ? "password" : "text"}
              autoComplete={hasPassword ? "current-password" : "off"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={!!(deleteErrors.password ?? deleteErrors.confirm)}
              helperText={deleteErrors.password ?? deleteErrors.confirm}
              autoFocus
              required
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button type="submit" color="error" variant="contained" disabled={!password || deleteAccount.isPending}>
              Delete permanently
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </Section>
  );
};

export const ProfilePage = () => {
  const [toast, setToast] = useState<string | null>(null);
  const { data: profile, isLoading, error } = useQuery({
    queryKey: ["profile"],
    queryFn: async () => (await api.get<Profile>("profile/")).data,
  });

  return (
    <Container maxWidth="md" sx={{ py: { xs: 3, md: 6 } }}>
      {isLoading && (
        <Box sx={{ display: "grid", placeItems: "center", py: 10 }}>
          <CircularProgress />
        </Box>
      )}
      {error && <Alert severity="error">{getErrorMessage(error)}</Alert>}
      {profile && (
        <Stack spacing={3}>
          <Stack direction="row" spacing={2.5} alignItems="center" mb={1}>
            <Avatar sx={{ width: 64, height: 64, bgcolor: "primary.main", fontSize: 28 }}>
              {(profile.display_name || profile.username)[0]?.toUpperCase()}
            </Avatar>
            <Box minWidth={0}>
              <Typography variant="h4" component="h1" noWrap>
                {profile.display_name || profile.username}
              </Typography>
              <Typography color="text.secondary">
                @{profile.username} · Member since{" "}
                {new Date(profile.date_joined).toLocaleDateString([], { month: "long", year: "numeric" })}
              </Typography>
            </Box>
          </Stack>
          <ProfileDetails profile={profile} onSaved={() => setToast("Profile saved")} />
          <Section title="Reminders" description="A short daily email with your plan steps.">
            <ReminderSettings />
          </Section>
          <ChangePassword hasPassword={profile.has_password} onSaved={() => setToast("Password updated")} />
          <PrivacyAndData hasPassword={profile.has_password} />
        </Stack>
      )}
      <Snackbar
        open={!!toast}
        autoHideDuration={3000}
        onClose={() => setToast(null)}
        message={toast}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      />
    </Container>
  );
};
