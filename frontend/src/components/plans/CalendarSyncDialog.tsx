import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import { ContentCopy, Event, Google, MailOutline } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import type { CalendarFeed } from "../../api/types";

const FEED_KEY = ["calendar-feed"];

type Platform = "apple" | "android" | "windows" | "other";

const platform = (): Platform => {
  const ua = navigator.userAgent;
  if (/iPhone|iPad|Macintosh/.test(ua)) return "apple";
  if (/Android/.test(ua)) return "android";
  if (/Windows/.test(ua)) return "windows";
  return "other";
};

/** One-click subscribe options, with the most likely one for this device first. */
const calendarOptions = (f: CalendarFeed) => {
  const options = [
    { key: "apple", label: "Apple or Outlook app", href: f.webcal_url ?? "", icon: <Event />, external: false },
    { key: "google", label: "Google Calendar", href: f.google_url ?? "", icon: <Google />, external: true },
    { key: "outlook", label: "Outlook.com", href: f.outlook_url ?? "", icon: <MailOutline />, external: true },
    { key: "office365", label: "Outlook (work or school)", href: f.office365_url ?? "", icon: <MailOutline />, external: true },
  ].filter((o) => o.href);
  const first = { apple: "apple", android: "google", windows: "outlook", other: "google" }[platform()];
  return [...options.filter((o) => o.key === first), ...options.filter((o) => o.key !== first)];
};

const COPY = {
  plans: {
    title: "Sync plans to your calendar",
    intro: "Subscribe once and your plan steps, and any therapy sessions you have scheduled, appear in your calendar. When something changes, your calendar updates on its own.",
    privacy: "Keep this link private: anyone with it can see your plan.",
    discreet: "Show events as “Personal check-in” or “Appointment” so others who see your calendar don't see the details.",
  },
  sessions: {
    title: "Sync sessions to your calendar",
    intro: "Subscribe once and your scheduled sessions appear in your calendar, updating when you reschedule or cancel. Clients appear by initials only.",
    privacy: "Keep this link private: anyone with it can see your session times.",
    discreet: "Show sessions as “Appointment”, without client initials.",
  },
};

/** Subscribe a calendar app to a private, auto-updating feed of the user's plans and sessions. */
export const CalendarSyncDialog = ({
  open,
  onClose,
  variant = "plans",
}: {
  open: boolean;
  onClose: () => void;
  variant?: keyof typeof COPY;
}) => {
  const copy = COPY[variant];
  const queryClient = useQueryClient();
  const [copied, setCopied] = useState(false);
  const feed = useQuery({
    queryKey: FEED_KEY,
    queryFn: async () => (await api.get<CalendarFeed>("account/calendar-feed/")).data,
    enabled: open,
  });
  const change = useMutation({
    mutationFn: async ({ method, data }: { method: "POST" | "PATCH" | "DELETE"; data?: object }) =>
      (await api.request<CalendarFeed>({ url: "account/calendar-feed/", method, data })).data,
    onSuccess: (data) => {
      queryClient.setQueryData(FEED_KEY, data);
      setCopied(false);
    },
  });
  const f = feed.data;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{copy.title}</DialogTitle>
      <DialogContent>
        <Typography color="text.secondary" mb={2}>
          {copy.intro}
        </Typography>
        {feed.isError && <Alert severity="error">{getErrorMessage(feed.error)}</Alert>}

        {f && !f.enabled && (
          <Button variant="contained" startIcon={<Event />} onClick={() => change.mutate({ method: "POST" })} disabled={change.isPending}>
            Create my calendar link
          </Button>
        )}

        {f?.enabled && (
          <Stack spacing={2.5}>
            <Box>
              <Box sx={{ display: "grid", gap: 1.25, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
                {calendarOptions(f).map((option, i) => (
                  <Button
                    key={option.key}
                    variant={i === 0 ? "contained" : "outlined"}
                    startIcon={option.icon}
                    href={option.href}
                    {...(option.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                  >
                    {option.label}
                  </Button>
                ))}
              </Box>
              <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                Your calendar opens and asks you to confirm. Google's phone app can't subscribe to links; add it on the
                web at calendar.google.com and it syncs to your phone.
              </Typography>
            </Box>
            <Box>
              <Stack direction="row" spacing={1}>
                <TextField size="small" label="Or paste this link into any calendar app" value={f.url} InputProps={{ readOnly: true }} />
                <Button
                  startIcon={<ContentCopy />}
                  onClick={() => {
                    navigator.clipboard?.writeText(f.url ?? "");
                    setCopied(true);
                  }}
                >
                  {copied ? "Copied" : "Copy"}
                </Button>
              </Stack>
              <Typography variant="caption" color="text.secondary">
                {copy.privacy} Google Calendar can take a few hours to pick up changes.
              </Typography>
            </Box>
            <FormControlLabel
              control={
                <Switch
                  checked={f.discreet}
                  onChange={(e) => change.mutate({ method: "PATCH", data: { discreet: e.target.checked } })}
                />
              }
              label={
                <Box>
                  <Typography>Discreet titles</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {copy.discreet}
                  </Typography>
                </Box>
              }
            />
            <Stack direction="row" spacing={1}>
              <Button size="small" onClick={() => change.mutate({ method: "POST" })}>
                Reset link
              </Button>
              <Button size="small" color="error" onClick={() => change.mutate({ method: "DELETE" })}>
                Turn off
              </Button>
            </Stack>
          </Stack>
        )}
        {change.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {getErrorMessage(change.error)}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Done</Button>
      </DialogActions>
    </Dialog>
  );
};
