import { Box, Container, Paper, Stack, Typography } from "@mui/material";
import {
  AssignmentTurnedInOutlined,
  AutoAwesomeOutlined,
  ChecklistRtl,
  EditNoteOutlined,
  FactCheckOutlined,
  LockOutlined,
  PersonSearchOutlined,
  ShowChart,
  ToggleOnOutlined,
  VerifiedUserOutlined,
} from "@mui/icons-material";
import { Navigate } from "@tanstack/react-router";
import { LinkButton } from "../components/RouterLink";
import { RequireAuth } from "../components/RouteGuards";
import { useAuth } from "../context/AuthContext";
import { Dashboard } from "./Dashboard";

const THERAPIST_FEATURES = [
  {
    icon: <AutoAwesomeOutlined />,
    title: "Walk in prepared",
    body: "What you worked on, what's still open, whether the homework happened, and how scores moved, in one brief before each session.",
  },
  {
    icon: <EditNoteOutlined />,
    title: "Notes in minutes",
    body: "Draft a SOAP or DAP note from a transcript or your rough notes. You review, edit and sign; nothing is final without you.",
  },
  {
    icon: <ShowChart />,
    title: "See progress",
    body: "PHQ-9 and GAD-7 over time, with a safety flag whenever item 9 is endorsed.",
  },
  {
    icon: <AssignmentTurnedInOutlined />,
    title: "Homework that follows them home",
    body: "Assign exercises that show up in your client's daily plan with reminders, and see completion if they choose to share it.",
  },
];

const TRUST = [
  { icon: <FactCheckOutlined />, title: "Every claim cited", body: "AI output links each point to the session it came from. Uncited claims are removed." },
  { icon: <VerifiedUserOutlined />, title: "You sign, it's final", body: "Drafts stay drafts. Signed notes can't be edited, only amended." },
  { icon: <ToggleOnOutlined />, title: "Clients stay in control", body: "Clients choose what you see between sessions and can change it any time." },
  { icon: <LockOutlined />, title: "Built for privacy", body: "Records are walled off per client, encrypted at rest, and every access is logged." },
];

const CLIENT_FEATURES = [
  { icon: <ChecklistRtl />, title: "Your therapist's plan, every day", body: "Exercises and reminders from your sessions, plus a companion to talk things through." },
  { icon: <PersonSearchOutlined />, title: "Find a therapist", body: "Not seeing someone yet? Find licensed providers near you, with a script for the first call." },
];

const FeatureCard = ({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) => (
  <Paper variant="outlined" sx={{ p: 3, borderRadius: 4, height: "100%" }}>
    <Box sx={{ width: 44, height: 44, borderRadius: 3, display: "grid", placeItems: "center", bgcolor: "action.hover", color: "primary.main", mb: 2 }}>
      {icon}
    </Box>
    <Typography variant="h6" gutterBottom>{title}</Typography>
    <Typography variant="body2" color="text.secondary">{body}</Typography>
  </Paper>
);

export const Home = () => {
  const { authenticated, user } = useAuth();

  // Signed-in users go to their own home: therapists to their practice, clients to their hub
  if (authenticated && user?.role === "therapist") return <Navigate to="/practice" replace />;
  if (authenticated) {
    return (
      <RequireAuth verified>
        <Dashboard />
      </RequireAuth>
    );
  }

  return (
    <>
      <Box sx={(theme) => ({ background: `radial-gradient(ellipse at top, ${theme.vars?.palette.primary.main ?? theme.palette.primary.main}22, transparent 60%)` })}>
        <Container maxWidth="md" sx={{ py: { xs: 8, md: 12 }, textAlign: "center" }}>
          <Typography variant="overline" color="primary" fontWeight={700} letterSpacing={2}>
            For therapists and the people they help
          </Typography>
          <Typography variant="h2" component="h1" sx={{ fontSize: { xs: "2.4rem", md: "3.5rem" }, mt: 1 }}>
            Every client's story, ready before the session
          </Typography>
          <Typography variant="h6" color="text.secondary" fontWeight={400} sx={{ mt: 3, maxWidth: 640, mx: "auto" }}>
            TherapyBot turns your notes, transcripts and screenings into a searchable memory for each client, so you can
            prep faster, document less, and see progress. Every answer cites the session it came from.
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} justifyContent="center" sx={{ mt: 5 }}>
            <LinkButton to="/therapists/register" variant="contained" size="large">I'm a therapist</LinkButton>
            <LinkButton to="/register" variant="outlined" size="large">I'm looking for support</LinkButton>
          </Stack>
        </Container>
      </Box>

      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
        <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" } }}>
          {THERAPIST_FEATURES.map((f) => <FeatureCard key={f.title} {...f} />)}
        </Box>
      </Container>

      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
        <Typography variant="h4" component="h2" textAlign="center" gutterBottom>Built for clinical trust</Typography>
        <Typography color="text.secondary" textAlign="center" mb={4}>It supports your judgment; it doesn't replace it.</Typography>
        <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" } }}>
          {TRUST.map((f) => <FeatureCard key={f.title} {...f} />)}
        </Box>
      </Container>

      <Container maxWidth="md" sx={{ py: { xs: 4, md: 8 } }}>
        <Paper variant="outlined" sx={{ p: { xs: 3, md: 5 }, borderRadius: 4 }}>
          <Typography variant="h5" component="h2" gutterBottom>For clients: support between sessions</Typography>
          <Typography color="text.secondary" mb={3}>
            When your therapist uses TherapyBot, the time between appointments follows the plan you made together.
          </Typography>
          <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
            {CLIENT_FEATURES.map((f) => <FeatureCard key={f.title} {...f} />)}
          </Box>
          <LinkButton to="/register" variant="contained" sx={{ mt: 3 }}>Create a free account</LinkButton>
        </Paper>
      </Container>
    </>
  );
};

export default Home;
