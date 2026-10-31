import { Alert, Box, Button, FormControlLabel, Stack, Switch, TextField, Typography } from "@mui/material";
import { NotificationsActiveOutlined } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import type { Profile } from "../../api/types";

const browserTimeZone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return "";
  }
};

const useReminderSettings = () => {
  const queryClient = useQueryClient();
  const profile = useQuery({ queryKey: ["profile"], queryFn: async () => (await api.get<Profile>("profile/")).data });
  const update = useMutation({
    // Always send the browser's time zone so reminders arrive at the right local time
    mutationFn: async (data: Partial<Profile>) =>
      (await api.patch<Profile>("profile/", { ...data, timezone: browserTimeZone() || undefined })).data,
    onSuccess: (data) => queryClient.setQueryData(["profile"], data),
  });
  return { profile: profile.data, update };
};

/** Full reminder controls, for the profile page. */
export const ReminderSettings = () => {
  const { profile, update } = useReminderSettings();
  if (!profile) return null;

  return (
    <Stack spacing={2}>
      <FormControlLabel
        control={
          <Switch
            checked={profile.reminders_enabled}
            onChange={(e) => update.mutate({ reminders_enabled: e.target.checked })}
          />
        }
        label="Email me a daily reminder of my plan"
      />
      {profile.reminders_enabled && (
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
          <TextField
            type="time"
            size="small"
            label="Send at"
            value={profile.reminder_time.slice(0, 5)}
            onChange={(e) => e.target.value && update.mutate({ reminder_time: e.target.value })}
            InputLabelProps={{ shrink: true }}
            sx={{ maxWidth: 180 }}
          />
          <Typography variant="body2" color="text.secondary">
            Time zone: {profile.timezone || browserTimeZone() || "server default"}. Each email lists that day's steps with
            one-tap “done” links. Days with nothing left to do are skipped.
          </Typography>
        </Stack>
      )}
      {update.isError && <Alert severity="error">{getErrorMessage(update.error)}</Alert>}
    </Stack>
  );
};

/** A one-tap prompt shown on the Plans page until reminders are on. */
export const ReminderNudge = () => {
  const { profile, update } = useReminderSettings();
  if (!profile || profile.reminders_enabled) return null;

  return (
    <Alert
      icon={<NotificationsActiveOutlined />}
      severity="info"
      action={
        <Button color="inherit" size="small" onClick={() => update.mutate({ reminders_enabled: true })} disabled={update.isPending}>
          Turn on
        </Button>
      }
    >
      <Box>
        <strong>Want a nudge?</strong> Get a short email each morning with today's steps and one-tap check-ins.
      </Box>
    </Alert>
  );
};
