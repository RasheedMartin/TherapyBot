import { useState } from "react";
import {
  Box,
  Button,
  Collapse,
  Container,
  Paper,
  Skeleton,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import api from "../api/client";
import type { CareTeamMember, ClientSession, MyCheckIn, TherapistOverview } from "../api/types";
import { CompleteCheckInDialog } from "../components/care/CheckInsCard";
import { useMyCheckIns } from "../components/care/useMyCheckIns";
import { DisconnectDialog, SharingSwitches } from "../components/CareTeamSection";
import { CalendarSyncDialog } from "../components/plans/CalendarSyncDialog";
import { formatDate, formatTime } from "../components/practice/format";
import { LinkButton, RouterLink } from "../components/RouterLink";

const longDate = (iso: string) =>
  new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
const isToday = (iso: string) => iso === new Date().toLocaleDateString("en-CA");
const firstName = (name: string) => name.split(/[ ,]/)[0];

const Section = ({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) => (
  <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4 }}>
    <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5} spacing={1}>
      <Typography variant="h6" component="h2">{title}</Typography>
      {action}
    </Stack>
    {children}
  </Paper>
);

const Empty = ({ children }: { children: React.ReactNode }) => <Typography color="text.secondary">{children}</Typography>;

const Sessions = ({ data }: { data: TherapistOverview }) => {
  const [syncing, setSyncing] = useState(false);
  const sessions: ClientSession[] = data.sessions ?? [];
  const next = sessions.find((s) => s.status === "scheduled");
  const rest = sessions.filter((s) => s !== next);
  return (
    <Section
      title="Sessions"
      action={next && <Button size="small" onClick={() => setSyncing(true)}>Add to my calendar</Button>}
    >
      {next ? (
        <Box mb={rest.length ? 2 : 0}>
          <Typography color="text.secondary">Next</Typography>
          <Typography variant="h5" component="p">
            {isToday(next.date) ? "Today" : longDate(next.date)}
            {next.start_time && ` at ${formatTime(next.start_time)}`}
          </Typography>
          <Typography color="text.secondary">{next.duration_minutes} minutes</Typography>
        </Box>
      ) : (
        <Empty>No session scheduled yet. {firstName(data.therapist.name)} will schedule the next one with you.</Empty>
      )}
      {rest.map((s) => (
        <Typography key={s.id} variant="body2" sx={{ py: 0.5, borderTop: 1, borderColor: "divider" }}
                    color={s.status === "cancelled" ? "text.secondary" : "text.primary"}>
          {longDate(s.date)}{s.start_time && ` at ${formatTime(s.start_time)}`}
          {s.status === "cancelled" && " (cancelled)"}
        </Typography>
      ))}
      {data.last_session && (
        <Typography variant="body2" color="text.secondary" mt={1.5}>
          Last session {formatDate(data.last_session)}. {data.sessions_attended} session{data.sessions_attended === 1 ? "" : "s"} together so far.
        </Typography>
      )}
      <CalendarSyncDialog open={syncing} onClose={() => setSyncing(false)} />
    </Section>
  );
};

const CheckIns = ({ data, checkIns }: { data: TherapistOverview; checkIns: MyCheckIn[] }) => {
  const [open, setOpen] = useState<MyCheckIn | null>(null);
  const due = checkIns.filter((c) => c.due);
  const upcoming = checkIns.filter((c) => !c.due);
  const completed = data.completed_checkins ?? [];
  if (!checkIns.length && !completed.length && !open) return null;
  return (
    <Section title="Check-ins">
      <Stack spacing={1.5}>
        {due.map((c) => (
          <Stack key={c.id} direction="row" spacing={1.5} alignItems="center">
            <Box sx={{ flex: 1 }}>
              <Typography fontWeight={600}>{c.instrument.name}</Typography>
              <Typography variant="body2" color="text.secondary">
                Ready now, {c.instrument.items.length} question{c.instrument.items.length === 1 ? "" : "s"}
              </Typography>
            </Box>
            <Button variant="contained" onClick={() => setOpen(c)}>Start</Button>
          </Stack>
        ))}
        {upcoming.map((c) => (
          <Typography key={c.id} variant="body2">
            {c.instrument.name}: next one on {formatDate(c.due_on)}
          </Typography>
        ))}
      </Stack>
      {completed.length > 0 && (
        <Typography variant="body2" color="text.secondary" mt={due.length || upcoming.length ? 2 : 0}>
          Last one you sent: {completed[0].name} on {formatDate(completed[0].date)}.
        </Typography>
      )}
      <CompleteCheckInDialog checkIn={open} onClose={() => setOpen(null)} />
    </Section>
  );
};

const Summaries = ({ data }: { data: TherapistOverview }) => {
  const [showEarlier, setShowEarlier] = useState(false);
  const [latest, ...earlier] = data.summaries ?? [];
  const when = (s: { session_date: string | null; shared_at: string }) =>
    s.session_date ? `Session on ${longDate(s.session_date)}` : `Shared ${longDate(s.shared_at)}`;
  return (
    <Section title="From your sessions">
      {!latest ? (
        <Empty>When {firstName(data.therapist.name)} shares a summary after a session, it shows here.</Empty>
      ) : (
        <>
          <Typography variant="body2" color="text.secondary">{when(latest)}</Typography>
          <Typography sx={{ mt: 0.5, whiteSpace: "pre-wrap", maxWidth: 720 }}>{latest.text}</Typography>
          {earlier.length > 0 && (
            <Box mt={2}>
              <Button size="small" sx={{ ml: -1 }} onClick={() => setShowEarlier((v) => !v)}>
                {showEarlier ? "Hide earlier summaries" : `Show earlier summaries (${earlier.length})`}
              </Button>
              <Collapse in={showEarlier} unmountOnExit>
                <Stack spacing={2} mt={1.5}>
                  {earlier.map((s) => (
                    <Box key={s.id} sx={{ pt: 1.5, borderTop: 1, borderColor: "divider" }}>
                      <Typography variant="body2" color="text.secondary">{when(s)}</Typography>
                      <Typography sx={{ mt: 0.5, whiteSpace: "pre-wrap", maxWidth: 720 }}>{s.text}</Typography>
                    </Box>
                  ))}
                </Stack>
              </Collapse>
            </Box>
          )}
        </>
      )}
    </Section>
  );
};

const Goals = ({ data }: { data: TherapistOverview }) => (
  <Section title="Goals you're working on">
    {data.goals?.length ? (
      <Stack component="ol" spacing={1.5} sx={{ m: 0, pl: 2.5 }}>
        {data.goals.map((g, i) => (
          <li key={i}>
            <Typography fontWeight={600}>{g.text}</Typography>
            {g.objectives.length > 0 && (
              <Box component="ul" sx={{ m: 0, mt: 0.5, pl: 2.5 }}>
                {g.objectives.map((o, j) => (
                  <Typography key={j} component="li" variant="body2" color="text.secondary">{o}</Typography>
                ))}
              </Box>
            )}
          </li>
        ))}
      </Stack>
    ) : (
      <Empty>If {firstName(data.therapist.name)} shares the goals from your treatment plan, they show here.</Empty>
    )}
  </Section>
);

const Homework = ({ data }: { data: TherapistOverview }) => (
  <Section
    title="Homework"
    action={data.homework?.length ? <LinkButton to="/plans" size="small">Open plans</LinkButton> : undefined}
  >
    {data.homework?.length ? (
      <Stack spacing={1.5}>
        {data.homework.map((h) => (
          <Box key={h.id}>
            {(data.homework?.length ?? 0) > 1 && <Typography fontWeight={600}>{h.title}</Typography>}
            {h.steps.map((s, i) => <Typography key={i} variant="body2" color="text.secondary">{s}</Typography>)}
          </Box>
        ))}
      </Stack>
    ) : (
      <Empty>Nothing assigned right now. Homework from {firstName(data.therapist.name)} appears in Plans with reminders.</Empty>
    )}
  </Section>
);

const Sharing = ({ member }: { member: CareTeamMember }) => {
  const navigate = useNavigate();
  const [leaving, setLeaving] = useState(false);
  return (
    <Section title="What they can see">
      <Typography variant="body2" color="text.secondary">
        They never see your chats live. Anything you mark private in a chat stays private.
      </Typography>
      <SharingSwitches member={member} />
      <Button size="small" color="error" sx={{ mt: 1.5, ml: -1 }} onClick={() => setLeaving(true)}>
        Disconnect from {firstName(member.therapist_name)}
      </Button>
      <DisconnectDialog member={leaving ? member : null} onClose={() => setLeaving(false)}
                        onDone={() => navigate({ to: "/" })} />
    </Section>
  );
};

/**
 * Everything about one therapist, from the client's side: sessions, check-ins, what they've shared
 * (summaries, goals, homework) and what the client shares back. The therapist's private notes never appear.
 */
export const MyTherapistPage = () => {
  const { id } = useSearch({ from: "/my-therapist" });
  const navigate = useNavigate();
  const team = useQuery({
    queryKey: ["care-team"],
    queryFn: async () => (await api.get<CareTeamMember[]>("care-team/")).data,
  });
  const members = [...(team.data ?? [])].sort((a, b) => (a.status === b.status ? 0 : a.status === "active" ? -1 : 1));
  const selected = members.find((m) => m.id === id) ?? members[0];
  const selectedId = selected?.id;
  const overview = useQuery({
    queryKey: ["therapist-overview", selectedId],
    queryFn: async () => (await api.get<TherapistOverview>(`care-team/${selectedId}/overview/`)).data,
    enabled: selectedId != null,
  });
  const checkIns = useMyCheckIns();
  const data = overview.data;

  if (team.data && !selected) {
    return (
      <Container maxWidth="sm" sx={{ py: { xs: 3, md: 6 } }}>
        <Typography variant="h4" component="h1" mb={1}>Your therapist</Typography>
        <Typography color="text.secondary" mb={3}>
          You're not connected with a therapist on TherapyBot. If yours uses it, they can invite you by email.
          Otherwise, Find care helps you look for one near you.
        </Typography>
        <LinkButton to="/find-care" variant="contained">Find care near me</LinkButton>
      </Container>
    );
  }

  const ended = data?.relationship.status === "ended";
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 6 } }}>
      {members.length > 1 && (
        <ToggleButtonGroup exclusive size="small" value={selected?.id} sx={{ mb: 3, flexWrap: "wrap" }}
                           onChange={(_, v) => v && navigate({ to: "/my-therapist", search: { id: v } })}>
          {members.map((m) => (
            <ToggleButton key={m.id} value={m.id}>
              {m.therapist_name}{m.status === "ended" && " (past)"}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      )}

      {!data ? (
        <Skeleton variant="text" width={320} height={56} />
      ) : (
        <Box mb={4}>
          <Typography variant="h4" component="h1">{data.therapist.name}</Typography>
          <Typography color="text.secondary">
            {[data.therapist.specialty, data.therapist.practice_name].filter(Boolean).join(", ")}
          </Typography>
          <Typography variant="body2" color="text.secondary" mt={0.5}>
            {ended
              ? `Your care together ended ${formatDate(data.relationship.ended_at)}.`
              : `Connected since ${formatDate(data.relationship.consented_at)}.`}
          </Typography>
        </Box>
      )}

      {data && ended && (
        <Typography color="text.secondary" maxWidth={640}>
          They no longer see anything from TherapyBot, and what they shared with you here has been removed with the
          connection. Your own chats, plans and check-in answers are still yours. See <RouterLink to="/profile">Profile</RouterLink> for
          your other connections.
        </Typography>
      )}

      {data && !ended && (
        <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "3fr 2fr" }, alignItems: "start" }}>
          <Stack spacing={3}>
            <Sessions data={data} />
            <CheckIns data={data} checkIns={(checkIns.data ?? []).filter((c) => c.relationship === data.relationship.id)} />
            <Summaries data={data} />
          </Stack>
          <Stack spacing={3}>
            <Goals data={data} />
            <Homework data={data} />
            <Sharing member={data.relationship} />
          </Stack>
        </Box>
      )}
    </Container>
  );
};
