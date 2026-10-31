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
import { ContentCopy, Google, Event } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import type { CalendarFeed } from "../../api/types";

const FEED_KEY = ["calendar-feed"];

/** Subscribe a calendar app to a private, auto-updating feed of the user's plans. */
export const CalendarSyncDialog = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
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
      <DialogTitle>Sync plans to your calendar</DialogTitle>
      <DialogContent>
        <Typography color="text.secondary" mb={2}>
          Subscribe once and your plan steps appear as recurring events. When you edit a plan, your calendar updates on
          its own.
        </Typography>
        {feed.isError && <Alert severity="error">{getErrorMessage(feed.error)}</Alert>}

        {f && !f.enabled && (
          <Button variant="contained" startIcon={<Event />} onClick={() => change.mutate({ method: "POST" })} disabled={change.isPending}>
            Create my calendar link
          </Button>
        )}

        {f?.enabled && (
          <Stack spacing={2.5}>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
              <Button variant="contained" startIcon={<Google />} href={f.google_url ?? ""} target="_blank" rel="noopener noreferrer">
                Add to Google Calendar
              </Button>
              <Button variant="outlined" startIcon={<Event />} href={f.webcal_url ?? ""}>
                Apple / Outlook
              </Button>
            </Stack>
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
                Keep this link private: anyone with it can see your plan. Google Calendar can take a few hours to pick up
                changes.
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
                    Show events as “Personal check-in” so others who see your calendar don't see the details.
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
