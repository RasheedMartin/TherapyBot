import { useState } from "react";
import { Alert, Box, Button, Container, Paper, Skeleton, Stack, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import api, { getErrorMessage } from "../../api/client";
import { MODALITIES, type PracticeOverview as Overview, type ScheduledSession } from "../../api/types";
import { formatDate, formatTime } from "../../components/practice/format";
import { RiskFlagInbox } from "../../components/practice/RiskFlagInbox";
import { ScheduleSessionDialog } from "../../components/practice/ScheduleSessionDialog";
import { SyntheticDataBanner } from "../../components/practice/SyntheticDataBanner";
import { useAuth } from "../../context/AuthContext";

const greeting = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
};

const WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"];
const plural = (n: number, one: string, many: string) => `${WORDS[n] ?? n} ${n === 1 ? one : many}`;

/** One sentence with the day's shape, in place of a row of stat tiles. */
const summary = (o: Overview) => {
  const first = o.today.find((s) => s.start_time);
  const day = o.today.length
    ? `${plural(o.today.length, "session", "sessions")} today${first ? `, the first at ${formatTime(first.start_time)}` : ""}.`
    : "No sessions today.";
  const todo = o.to_close.length + o.needs_note.length + o.drafts.length + o.open_flags;
  return `${day} ${todo ? `${plural(todo, "thing needs", "things need")} your attention.` : "Nothing needs your attention."}`;
};

/** Today as a timeline: the time carries the eye down the day, each session has one next step. */
const TodayTimeline = ({ sessions, onSchedule }: { sessions: ScheduledSession[]; onSchedule: () => void }) => {
  const navigate = useNavigate();
  if (!sessions.length) {
    return (
      <Stack spacing={1.5} alignItems="flex-start">
        <Typography color="text.secondary">Nothing on the calendar today.</Typography>
        <Button variant="outlined" onClick={onSchedule}>Schedule a session</Button>
      </Stack>
    );
  }
  return (
    <Box component="ol" sx={{ listStyle: "none", m: 0, p: 0 }}>
      {sessions.map((s, i) => (
        <Box component="li" key={s.id} sx={{ display: "grid", gridTemplateColumns: "84px 20px 1fr", alignItems: "stretch" }}>
          <Typography sx={{ pt: 1.75, fontVariantNumeric: "tabular-nums", fontWeight: 600, color: "primary.dark" }}>
            {s.start_time ? formatTime(s.start_time) : "Any time"}
          </Typography>
          {/* The rail: a dot per session joined by a line, so the day reads top to bottom */}
          <Box sx={{ position: "relative", display: "flex", justifyContent: "center" }}>
            <Box sx={{ position: "absolute", top: i === 0 ? 24 : 0, bottom: i === sessions.length - 1 ? "calc(100% - 24px)" : 0,
                       width: 2, bgcolor: "divider" }} />
            <Box sx={{ position: "relative", mt: 2.25, width: 12, height: 12, borderRadius: "50%",
                       bgcolor: s.status === "completed" ? "primary.main" : "background.paper",
                       border: 2, borderColor: "primary.main" }} />
          </Box>
          <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={2}
                 sx={{ py: 1.25, pl: 1.5, borderBottom: i === sessions.length - 1 ? 0 : 1, borderColor: "divider" }}>
            <Box minWidth={0}>
              <Typography fontWeight={600} noWrap>{s.client_name}</Typography>
              <Typography variant="body2" color="text.secondary">
                {s.duration_minutes} minutes, {MODALITIES.find((m) => m.value === s.modality)?.label}
                {s.status === "completed" && ", completed"}
              </Typography>
            </Box>
            <Button size="small" variant={i === 0 && s.status === "scheduled" ? "contained" : "outlined"} sx={{ flexShrink: 0 }}
                    onClick={() => navigate({ to: "/practice/clients/$clientId", params: { clientId: String(s.client_id) } })}>
              Prep
            </Button>
          </Stack>
        </Box>
      ))}
    </Box>
  );
};

type Task = { key: string; title: string; detail: string; action: React.ReactNode };

/** Everything waiting on the therapist, as one list ordered by what blocks what. */
const AttentionList = ({ overview, onSchedule }: { overview: Overview; onSchedule: (clientId: number) => void }) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const close = useMutation({
    mutationFn: ({ session, status }: { session: ScheduledSession; status: "completed" | "cancelled" }) =>
      api.patch(`practice/clients/${session.client_id}/sessions/${session.id}/`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["practice-overview"] });
      queryClient.invalidateQueries({ queryKey: ["schedule"] });
    },
  });
  const openClient = (clientId: number) =>
    navigate({ to: "/practice/clients/$clientId", params: { clientId: String(clientId) } });

  const tasks: Task[] = [
    ...overview.to_close.map((s) => ({
      key: `close-${s.id}`,
      title: `Did ${s.client_name}'s session happen?`,
      detail: `Scheduled ${formatDate(s.date)}${s.start_time ? ` at ${formatTime(s.start_time)}` : ""}`,
      action: (
        <Stack direction="row" spacing={1}>
          <Button size="small" variant="outlined" disabled={close.isPending} onClick={() => close.mutate({ session: s, status: "completed" })}>
            Mark completed
          </Button>
          <Button size="small" disabled={close.isPending} onClick={() => close.mutate({ session: s, status: "cancelled" })}>
            It was cancelled
          </Button>
        </Stack>
      ),
    })),
    ...overview.needs_note.map((s) => ({
      key: `note-${s.id}`,
      title: `Write a note for ${s.client_name}`,
      detail: `Session on ${formatDate(s.date)} has no progress note yet`,
      action: <Button size="small" variant="outlined" onClick={() => openClient(s.client_id)}>Write note</Button>,
    })),
    ...overview.drafts.map((d) => ({
      key: `draft-${d.id}`,
      title: `Sign ${d.client_name}'s note`,
      detail: `${d.title}, still a draft`,
      action: (
        <Button size="small" variant="outlined"
                onClick={() => navigate({ to: "/practice/clients/$clientId/documents/$docId",
                                          params: { clientId: String(d.client_id), docId: String(d.id) } })}>
          Review and sign
        </Button>
      ),
    })),
    ...overview.unscheduled.map((c) => ({
      key: `unscheduled-${c.id}`,
      title: `Nothing scheduled with ${c.display_name}`,
      detail: "No upcoming session on the calendar",
      action: <Button size="small" onClick={() => onSchedule(c.id)}>Schedule</Button>,
    })),
  ];

  if (!tasks.length) return <Typography color="text.secondary">You're all caught up: notes are written and signed, and everyone has a next session.</Typography>;
  return (
    <Stack divider={<Box sx={{ borderTop: 1, borderColor: "divider" }} />}>
      {tasks.map((t) => (
        <Stack key={t.key} direction={{ xs: "column", sm: "row" }} spacing={1} justifyContent="space-between"
               alignItems={{ sm: "center" }} sx={{ py: 1.5 }}>
          <Box minWidth={0}>
            <Typography fontWeight={600}>{t.title}</Typography>
            <Typography variant="body2" color="text.secondary">{t.detail}</Typography>
          </Box>
          <Box sx={{ flexShrink: 0 }}>{t.action}</Box>
        </Stack>
      ))}
      {close.isError && <Alert severity="error">{getErrorMessage(close.error)}</Alert>}
    </Stack>
  );
};

/** The therapist's home: today, and what's waiting on them across clients. */
export const PracticeOverview = () => {
  const { user } = useAuth();
  const [schedulingFor, setSchedulingFor] = useState<number | null | undefined>(undefined); // null = pick a client
  const overview = useQuery({
    queryKey: ["practice-overview"],
    queryFn: async () => (await api.get<Overview>("practice/overview/")).data,
  });
  const o = overview.data;

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Typography variant="h4" component="h1">{greeting()}, {user?.display_name}.</Typography>
      <Typography color="text.secondary" sx={{ mt: 0.5, mb: 3, maxWidth: 640 }}>
        {o ? summary(o) : " "}
      </Typography>
      <Stack spacing={3}>
        <SyntheticDataBanner />
        {overview.isError && <Alert severity="error">{getErrorMessage(overview.error)}</Alert>}
        <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "5fr 6fr" }, alignItems: "start" }}>
          <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4 }}>
            <Typography variant="h6" component="h2" mb={1}>Today</Typography>
            {overview.isLoading ? <Skeleton variant="rounded" height={160} />
              : o && <TodayTimeline sessions={o.today} onSchedule={() => setSchedulingFor(null)} />}
          </Paper>
          <Stack spacing={3}>
            {!!o?.open_flags && <RiskFlagInbox />}
            <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4 }}>
              <Typography variant="h6" component="h2">Needs attention</Typography>
              {overview.isLoading ? <Skeleton variant="rounded" height={160} sx={{ mt: 1 }} />
                : o && <AttentionList overview={o} onSchedule={(id) => setSchedulingFor(id)} />}
            </Paper>
          </Stack>
        </Box>
      </Stack>
      {schedulingFor !== undefined && (
        <ScheduleSessionDialog open clientId={schedulingFor ?? undefined}
                               onClose={() => { setSchedulingFor(undefined); overview.refetch(); }} />
      )}
    </Container>
  );
};
