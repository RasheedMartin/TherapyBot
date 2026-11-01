import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  ButtonBase,
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import {
  Add,
  CheckCircleOutline,
  ChevronLeft,
  ChevronRight,
  EventBusyOutlined,
  EventOutlined,
  OpenInNew,
} from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import api, { getErrorMessage } from "../../api/client";
import type { ScheduledSession, SessionStatus } from "../../api/types";
import { CalendarSyncDialog } from "../plans/CalendarSyncDialog";
import { formatTime } from "./format";
import { ScheduleSessionDialog } from "./ScheduleSessionDialog";

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const startOfWeek = (d: Date) => {
  const monday = new Date(d);
  monday.setHours(12, 0, 0, 0);
  monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return monday;
};

const addDays = (d: Date, n: number) => {
  const next = new Date(d);
  next.setDate(d.getDate() + n);
  return next;
};

const SessionChip = ({ session, onClick }: { session: ScheduledSession; onClick: (el: HTMLElement) => void }) => {
  const cancelled = session.status === "cancelled";
  return (
    <ButtonBase
      onClick={(e) => onClick(e.currentTarget)}
      sx={{
        display: "block", width: "100%", textAlign: "left", p: 1, borderRadius: 2, border: 1,
        borderColor: session.status === "scheduled" ? "primary.main" : "divider",
        bgcolor: session.status === "scheduled" ? "action.hover" : "transparent",
        opacity: cancelled ? 0.55 : 1,
      }}
    >
      <Typography variant="caption" color="text.secondary" display="block">
        {formatTime(session.start_time)} · {session.duration_minutes} min
      </Typography>
      <Typography variant="body2" fontWeight={600} noWrap sx={{ textDecoration: cancelled ? "line-through" : "none" }}>
        {session.client_name}
      </Typography>
      {session.status === "completed" && <Typography variant="caption" color="success.main">Completed</Typography>}
    </ButtonBase>
  );
};

/** The therapist's week across clients: see it, schedule into it, and keep sessions' status current. */
export const WeekSchedule = () => {
  const theme = useTheme();
  const wide = useMediaQuery(theme.breakpoints.up("md"));
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [scheduling, setScheduling] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [menu, setMenu] = useState<{ el: HTMLElement; session: ScheduledSession } | null>(null);

  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const range = { start: iso(days[0]), end: iso(days[6]) };
  const today = iso(new Date());
  const schedule = useQuery({
    queryKey: ["schedule", range.start],
    queryFn: async () =>
      (await api.get<{ sessions: ScheduledSession[] }>("practice/schedule/", { params: range })).data.sessions,
  });

  const setStatus = useMutation({
    mutationFn: ({ session, status }: { session: ScheduledSession; status: SessionStatus }) =>
      api.patch(`practice/clients/${session.client_id}/sessions/${session.id}/`, { status }),
    onSuccess: (_, { session }) => {
      queryClient.invalidateQueries({ queryKey: ["schedule"] });
      queryClient.invalidateQueries({ queryKey: ["timeline", session.client_id] });
    },
  });

  const label = `${days[0].toLocaleDateString([], { month: "short", day: "numeric" })} – ${days[6].toLocaleDateString([], {
    month: days[0].getMonth() === days[6].getMonth() ? undefined : "short",
    day: "numeric",
  })}`;
  const sessionsOn = (d: Date) => schedule.data?.filter((s) => s.date === iso(d)) ?? [];
  const upcoming = schedule.data?.filter((s) => s.status === "scheduled").length ?? 0;
  // Read once here: the React Compiler evaluates values used in handlers during render, so `menu!` would throw
  const selected = menu?.session ?? null;
  const changeStatus = (status: SessionStatus) => {
    if (selected) setStatus.mutate({ session: selected, status });
    setMenu(null);
  };

  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4 }}>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} spacing={1.5} mb={2}>
        <Stack direction="row" alignItems="center" spacing={0.5} flexWrap="wrap" useFlexGap>
          <Typography variant="h6" component="h2" sx={{ mr: 1 }}>Schedule</Typography>
          <IconButton size="small" aria-label="Previous week" onClick={() => setWeekStart(addDays(weekStart, -7))}><ChevronLeft /></IconButton>
          <Typography fontWeight={600} sx={{ minWidth: 110, textAlign: "center" }}>{label}</Typography>
          <IconButton size="small" aria-label="Next week" onClick={() => setWeekStart(addDays(weekStart, 7))}><ChevronRight /></IconButton>
          <Button size="small" onClick={() => setWeekStart(startOfWeek(new Date()))}>Today</Button>
        </Stack>
        <Stack direction="row" spacing={1}>
          <Tooltip title="Subscribe in Google, Apple or Outlook Calendar" describeChild>
            <Button size="small" startIcon={<EventOutlined />} onClick={() => setSyncing(true)}>Sync calendar</Button>
          </Tooltip>
          <Button size="small" variant="contained" startIcon={<Add />} onClick={() => setScheduling(true)}>Schedule</Button>
        </Stack>
      </Stack>

      {schedule.isError && <Alert severity="error">{getErrorMessage(schedule.error)}</Alert>}
      {schedule.isLoading && <Skeleton variant="rounded" height={140} />}
      {schedule.data && (
        <>
          <Box sx={{ display: "grid", gap: 1, gridTemplateColumns: wide ? "repeat(7, minmax(0, 1fr))" : "1fr" }}>
            {days.map((d) => {
              const items = sessionsOn(d);
              if (!wide && !items.length) return null;
              const isToday = iso(d) === today;
              return (
                <Box key={iso(d)} sx={{ minHeight: wide ? 120 : 0, p: 1, borderRadius: 2,
                                        bgcolor: isToday ? "action.selected" : "transparent" }}>
                  <Typography variant="caption" fontWeight={isToday ? 700 : 500} color={isToday ? "primary" : "text.secondary"}
                              display="block" mb={0.75}>
                    {d.toLocaleDateString([], { weekday: "short", day: "numeric", month: wide ? undefined : "short" })}
                  </Typography>
                  <Stack spacing={0.75}>
                    {items.map((s) => <SessionChip key={s.id} session={s} onClick={(el) => setMenu({ el, session: s })} />)}
                  </Stack>
                </Box>
              );
            })}
          </Box>
          <Typography variant="caption" color="text.secondary" display="block" mt={1.5}>
            {upcoming ? `${upcoming} scheduled this week.` : "Nothing scheduled this week."}
          </Typography>
        </>
      )}

      <Menu anchorEl={menu?.el} open={!!menu} onClose={() => setMenu(null)}>
        <MenuItem
          onClick={() => {
            if (selected) navigate({ to: "/practice/clients/$clientId", params: { clientId: String(selected.client_id) } });
          }}
        >
          <ListItemIcon><OpenInNew fontSize="small" /></ListItemIcon>Open client record
        </MenuItem>
        {selected && selected.status !== "completed" && (
          <MenuItem onClick={() => changeStatus("completed")}>
            <ListItemIcon><CheckCircleOutline fontSize="small" /></ListItemIcon>Mark completed
          </MenuItem>
        )}
        {selected?.status === "scheduled" && (
          <MenuItem onClick={() => changeStatus("cancelled")}>
            <ListItemIcon><EventBusyOutlined fontSize="small" /></ListItemIcon>Cancel session
          </MenuItem>
        )}
      </Menu>
      {scheduling && <ScheduleSessionDialog open onClose={() => setScheduling(false)} />}
      <CalendarSyncDialog open={syncing} onClose={() => setSyncing(false)} variant="sessions" />
    </Paper>
  );
};
