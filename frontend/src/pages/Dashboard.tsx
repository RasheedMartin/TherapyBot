import { Box, Container, LinearProgress, Paper, Stack, Typography } from "@mui/material";
import {
  ArrowForward,
  ChatBubbleOutline,
  ChecklistRtl,
  DescriptionOutlined,
  EventOutlined,
  PersonSearchOutlined,
  TuneOutlined,
} from "@mui/icons-material";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import {
  OUTREACH_STATUSES,
  type CareTeamMember,
  type Conversation,
  type Plan,
  type Profile,
  type SavedProvider,
} from "../api/types";
import { SessionSummaryCard } from "../components/care/SessionSummaryCard";
import { UpcomingSessions } from "../components/care/UpcomingSessions";
import { TodayList } from "../components/plans/TodayList";
import { PLANS_KEY } from "../components/plans/useCheckIn";
import { useAuth } from "../context/AuthContext";
import { LinkButton } from "../components/RouterLink";

/** A home-page card. The action sits at the bottom so buttons line up across a row of equal-height cards. */
const Card = ({
  icon,
  title,
  children,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) => (
  <Paper
    variant="outlined"
    sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4, height: "100%", display: "flex", flexDirection: "column" }}
  >
    <Stack direction="row" spacing={1} alignItems="center" mb={1.5} color="primary.main">
      {icon}
      <Typography variant="h6" component="h2" color="text.primary">
        {title}
      </Typography>
    </Stack>
    <Box sx={{ flex: 1 }}>{children}</Box>
    {action && <Box sx={{ mt: 2 }}>{action}</Box>}
  </Paper>
);

const greeting = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
};

/** Signed-in home: what to do next across chat, plans, and finding care. */
export const Dashboard = () => {
  const { user } = useAuth();
  const plans = useQuery({ queryKey: PLANS_KEY, queryFn: async () => (await api.get<Plan[]>("plans/")).data });
  const conversations = useQuery({
    queryKey: ["conversations"],
    queryFn: async () => (await api.get<Conversation[]>("conversations/")).data,
  });
  const shortlist = useQuery({
    queryKey: ["saved-providers"],
    queryFn: async () => (await api.get<SavedProvider[]>("saved-providers/")).data,
  });
  const profile = useQuery({ queryKey: ["profile"], queryFn: async () => (await api.get<Profile>("profile/")).data });

  const activePlans = plans.data?.filter((p) => !p.archived) ?? [];
  const lastConversation = conversations.data?.[0];
  const saved = shortlist.data ?? [];
  const scheduled = saved.some((s) => s.status === "scheduled");
  const contacted = saved.filter((s) => s.status !== "saved" && s.status !== "not_a_fit").length;
  const needsSetup = profile.data && (!profile.data.goals || !profile.data.zip_code);
  const team = useQuery({
    queryKey: ["care-team"],
    queryFn: async () => (await api.get<CareTeamMember[]>("care-team/")).data,
  });
  const careTeam = team.data?.filter((m) => m.status === "active") ?? [];

  // Clients with a therapist see their care; everyone else is offered help finding it
  const therapist = careTeam[0];
  const secondary = [
    therapist ? (
      <Card
        key="therapist"
        icon={<EventOutlined />}
        title="Your therapist"
        action={
          <LinkButton to="/profile" variant="text" endIcon={<ArrowForward />} sx={{ ml: -1 }}>
            What they can see
          </LinkButton>
        }
      >
        <Typography fontWeight={600}>{therapist.therapist_name}</Typography>
        {/* Upcoming sessions have their own section above; here, who they're seeing */}
        <Typography color="text.secondary">
          {therapist.next_session ? therapist.practice_name : "No upcoming session scheduled yet."}
        </Typography>
      </Card>
    ) : (
      <Card
        key="find-care"
        icon={<PersonSearchOutlined />}
        title="Finding a therapist"
        action={
          saved.length === 0 ? (
            <LinkButton to="/find-care" variant="outlined" endIcon={<ArrowForward />}>
              Find care near me
            </LinkButton>
          ) : (
            <LinkButton to="/find-care" search={{ tab: "shortlist" }} variant="outlined" endIcon={<ArrowForward />}>
              Open my shortlist
            </LinkButton>
          )
        }
      >
        {saved.length === 0 ? (
          <Typography color="text.secondary">
            See licensed providers near you on a map, save a shortlist, and get a script for the first call.
          </Typography>
        ) : (
          <>
            <Typography color="text.secondary" mb={1.5}>
              {scheduled
                ? "You have an appointment scheduled. That's a big step."
                : contacted
                  ? `You've reached out to ${contacted} of ${saved.length}. Keep going; it often takes a few calls.`
                  : `${saved.length} saved. Calling one is the next step, and we have a script to help.`}
            </Typography>
            <LinearProgress
              variant="determinate"
              value={scheduled ? 100 : (contacted / Math.max(saved.length, 1)) * 100}
              sx={{ height: 8, borderRadius: 4, mb: 1.5 }}
            />
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {OUTREACH_STATUSES.filter((o) => saved.some((s) => s.status === o.value)).map((o) => (
                <Typography key={o.value} variant="caption" color="text.secondary">
                  {saved.filter((s) => s.status === o.value).length} {o.label.toLowerCase()}
                </Typography>
              ))}
            </Stack>
          </>
        )}
      </Card>
    ),
    <Card
      key="notes"
      icon={<DescriptionOutlined />}
      title="After a session"
      action={
        <LinkButton to="/notes" variant="text" endIcon={<ArrowForward />} sx={{ ml: -1 }}>
          Understand my notes
        </LinkButton>
      }
    >
      <Typography color="text.secondary">
        Paste your therapist's notes or visit summary to get a plain-language explanation and a plan for your homework.
      </Typography>
    </Card>,
    needsSetup ? (
      <Card
        key="personalize"
        icon={<TuneOutlined />}
        title="Personalize TherapyBot"
        action={
          <LinkButton to="/profile" variant="text" endIcon={<ArrowForward />} sx={{ ml: -1 }}>
            Update profile
          </LinkButton>
        }
      >
        <Typography color="text.secondary">
          {!profile.data?.goals && "Tell us what you'd like to work on so conversations start where you are. "}
          {!profile.data?.zip_code && "Add your ZIP code to find care near you faster."}
        </Typography>
      </Card>
    ) : null,
  ].filter(Boolean);

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 6 } }}>
      <Typography variant="h4" component="h1">
        {greeting()}, {user?.display_name}.
      </Typography>
      <Typography color="text.secondary" mb={4}>
        Here's where things stand. Take whatever step feels doable today.
      </Typography>

      <Stack spacing={3}>
        {therapist && <UpcomingSessions />}
        {therapist && <SessionSummaryCard />}
        {/* What to do today, and the conversation to come back to: equal height, side by side on desktop */}
        <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "3fr 2fr" } }}>
          {activePlans.length > 0 ? (
            <TodayList plans={activePlans} />
          ) : (
            <Card
              icon={<ChecklistRtl />}
              title="Make a plan"
              action={
                <LinkButton to={lastConversation ? "/chat" : "/plans"} variant="outlined" endIcon={<ArrowForward />}>
                  {lastConversation ? "Open a chat, then tap “Make a plan”" : "Start a plan"}
                </LinkButton>
              }
            >
              <Typography color="text.secondary">
                Turn what you talk about into small daily steps, with reminders in your calendar.
              </Typography>
            </Card>
          )}

          <Card
            icon={<ChatBubbleOutline />}
            title="Talk it through"
            action={
              lastConversation ? (
                <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
                  <LinkButton to="/chat" search={{ c: lastConversation.id }} variant="contained">
                    Continue
                  </LinkButton>
                  <LinkButton to="/chat" variant="outlined">
                    New conversation
                  </LinkButton>
                </Stack>
              ) : (
                <LinkButton to="/chat" variant="contained">
                  Start a conversation
                </LinkButton>
              )
            }
          >
            <Typography color="text.secondary">
              {lastConversation ? (
                <>
                  Pick up where you left off: <strong>{lastConversation.title || "your last conversation"}</strong>
                </>
              ) : (
                "Share what's on your mind. There's no wrong place to start."
              )}
            </Typography>
          </Card>
        </Box>

        {/* Supporting steps: one row of equal cards */}
        <Box
          sx={{
            display: "grid",
            gap: 3,
            gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: `repeat(${secondary.length}, 1fr)` },
          }}
        >
          {secondary}
        </Box>
      </Stack>
    </Container>
  );
};
