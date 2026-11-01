import { useState } from "react";
import { Box, Button, Paper, Stack, Typography } from "@mui/material";
import { EventOutlined } from "@mui/icons-material";
import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import type { ClientSession } from "../../api/types";
import { CalendarSyncDialog } from "../plans/CalendarSyncDialog";
import { formatTime } from "../practice/format";

const longDate = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
const shortDate = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
const isToday = (iso: string) => iso === new Date().toLocaleDateString("en-CA");

/** The client's sessions with their therapist: the next one up front, later ones and cancellations below. */
export const UpcomingSessions = () => {
  const [syncing, setSyncing] = useState(false);
  const sessions = useQuery({
    queryKey: ["my-sessions"],
    queryFn: async () => (await api.get<ClientSession[]>("care-team/sessions/")).data,
  });
  const all = sessions.data ?? [];
  const next = all.find((s) => s.status === "scheduled");
  if (!next) {
    // Only cancellations ahead: still say so, so a cancelled session doesn't just vanish
    const cancelled = all.filter((s) => s.status === "cancelled");
    if (!cancelled.length) return null;
  }
  const later = all.filter((s) => s !== next);

  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4, borderColor: next ? "primary.main" : "divider" }}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} justifyContent="space-between" alignItems={{ sm: "center" }}>
        {next ? (
          <Box>
            <Typography color="text.secondary">Your next session</Typography>
            <Typography variant="h5" component="h2" sx={{ mt: 0.25 }}>
              {isToday(next.date) ? "Today" : longDate(next.date)}
              {next.start_time && ` at ${formatTime(next.start_time)}`}
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 0.5 }}>
              {next.duration_minutes} minutes with {next.therapist_name}
            </Typography>
          </Box>
        ) : (
          <Typography variant="h6" component="h2">Session updates</Typography>
        )}
        <Button variant="outlined" startIcon={<EventOutlined />} onClick={() => setSyncing(true)} sx={{ flexShrink: 0 }}>
          Add to my calendar
        </Button>
      </Stack>
      {later.length > 0 && (
        <Stack component="ul" spacing={0.5} sx={{ listStyle: "none", p: 0, m: 0, mt: 2, pt: 2, borderTop: 1, borderColor: "divider" }}>
          {later.map((s) => (
            <Typography component="li" key={s.id} variant="body2"
                        color={s.status === "cancelled" ? "error.main" : "text.secondary"}>
              {s.status === "cancelled" ? "Cancelled: " : ""}
              {shortDate(s.date)}{s.start_time && ` at ${formatTime(s.start_time)}`}
              {s.status === "scheduled" && `, ${s.therapist_name}`}
            </Typography>
          ))}
        </Stack>
      )}
      <CalendarSyncDialog open={syncing} onClose={() => setSyncing(false)} />
    </Paper>
  );
};
