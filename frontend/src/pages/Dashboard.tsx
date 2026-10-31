import { Box, Container, LinearProgress, Paper, Stack, Typography } from "@mui/material";
import {
  ArrowForward,
  ChatBubbleOutline,
  ChecklistRtl,
  DescriptionOutlined,
  PersonSearchOutlined,
  TuneOutlined,
} from "@mui/icons-material";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import { OUTREACH_STATUSES, type Conversation, type Plan, type Profile, type SavedProvider } from "../api/types";
import { TodayList } from "../components/plans/TodayList";
import { PLANS_KEY } from "../components/plans/useCheckIn";
import { useAuth } from "../context/AuthContext";
import { LinkButton } from "../components/RouterLink";

const Card = ({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) => (
  <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4, height: "100%" }}>
    <Stack direction="row" spacing={1} alignItems="center" mb={1.5} color="primary.main">
      {icon}
      <Typography variant="h6" component="h2" color="text.primary">
        {title}
      </Typography>
    </Stack>
    {children}
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

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 6 } }}>
      <Typography variant="h4" component="h1">
        {greeting()}, {user?.display_name}.
      </Typography>
      <Typography color="text.secondary" mb={4}>
        Here's where things stand. Take whatever step feels doable today.
      </Typography>

      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "3fr 2fr" }, alignItems: "start" }}>
        <Stack spacing={3}>
          {activePlans.length > 0 ? (
            <TodayList plans={activePlans} />
          ) : (
            <Card icon={<ChecklistRtl />} title="Make a plan">
              <Typography color="text.secondary" mb={2}>
                Turn what you talk about into small daily steps, with reminders in your calendar.
              </Typography>
              <LinkButton to={lastConversation ? "/chat" : "/plans"} variant="outlined" endIcon={<ArrowForward />}>
                {lastConversation ? "Open a chat, then tap “Make a plan”" : "Start a plan"}
              </LinkButton>
            </Card>
          )}

          <Card icon={<ChatBubbleOutline />} title="Talk it through">
            {lastConversation ? (
              <>
                <Typography color="text.secondary" mb={2}>
                  Pick up where you left off: <strong>{lastConversation.title || "your last conversation"}</strong>
                </Typography>
                <Stack direction="row" spacing={1.5}>
                  <LinkButton to="/chat" search={{ c: lastConversation.id }} variant="contained">
                    Continue
                  </LinkButton>
                  <LinkButton to="/chat" variant="outlined">
                    New conversation
                  </LinkButton>
                </Stack>
              </>
            ) : (
              <>
                <Typography color="text.secondary" mb={2}>
                  Share what's on your mind. There's no wrong place to start.
                </Typography>
                <LinkButton to="/chat" variant="contained">
                  Start a conversation
                </LinkButton>
              </>
            )}
          </Card>
        </Stack>

        <Stack spacing={3}>
          <Card icon={<PersonSearchOutlined />} title="Finding a therapist">
            {saved.length === 0 ? (
              <>
                <Typography color="text.secondary" mb={2}>
                  See licensed providers near you on a map, save a shortlist, and get a script for the first call.
                </Typography>
                <LinkButton to="/find-care" variant="outlined" endIcon={<ArrowForward />}>
                  Find care near me
                </LinkButton>
              </>
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
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap mb={2}>
                  {OUTREACH_STATUSES.filter((o) => saved.some((s) => s.status === o.value)).map((o) => (
                    <Typography key={o.value} variant="caption" color="text.secondary">
                      {saved.filter((s) => s.status === o.value).length} {o.label.toLowerCase()}
                    </Typography>
                  ))}
                </Stack>
                <LinkButton to="/find-care" search={{ tab: "shortlist" }} variant="outlined" endIcon={<ArrowForward />}>
                  Open my shortlist
                </LinkButton>
              </>
            )}
          </Card>

          <Card icon={<DescriptionOutlined />} title="After a session">
            <Typography color="text.secondary" mb={2}>
              Paste your therapist's notes or visit summary to get a plain-language explanation and a plan for your
              homework.
            </Typography>
            <LinkButton to="/notes" variant="text" endIcon={<ArrowForward />}>
              Understand my notes
            </LinkButton>
          </Card>

          {needsSetup && (
            <Card icon={<TuneOutlined />} title="Personalize TherapyBot">
              <Typography color="text.secondary" mb={2}>
                {!profile.data?.goals && "Tell us what you'd like to work on so conversations start where you are. "}
                {!profile.data?.zip_code && "Add your ZIP code to find care near you faster."}
              </Typography>
              <LinkButton to="/profile" variant="text" endIcon={<ArrowForward />}>
                Update profile
              </LinkButton>
            </Card>
          )}
        </Stack>
      </Box>
    </Container>
  );
};
