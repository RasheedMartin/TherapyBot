import { Box, Chip, Container, Paper, Stack, Typography } from "@mui/material";
import { Navigate } from "@tanstack/react-router";
import { LinkButton } from "../components/RouterLink";
import { RequireAuth } from "../components/RouteGuards";
import { useAuth } from "../context/AuthContext";
import { Dashboard } from "./Dashboard";

// The week as a therapist lives it: these are a real sequence, so they're numbered
const WEEK = [
  { when: "Before the session", what: "A brief of where things stand: what you covered, what's still open, whether the homework happened, how scores moved." },
  { when: "In the session", what: "Ask the record anything (“what did we try for sleep?”) and get an answer that points to the session it came from." },
  { when: "After the session", what: "A SOAP or DAP draft from your transcript or rough notes. You edit and sign; nothing is final without you." },
  { when: "Between sessions", what: "Homework shows up in your client's day with reminders, and you see what they choose to share." },
];

const TRUST = [
  { term: "Every claim is cited", detail: "AI output links each point to its source. Anything it can't trace is removed before you see it." },
  { term: "You sign, it's final", detail: "Drafts stay drafts. Signed notes are locked; corrections are added as addenda." },
  { term: "Clients stay in control", detail: "Clients choose what you see between sessions and can change it any time." },
  { term: "Private by design", detail: "Each client's record is walled off, encrypted at rest, and every access is logged." },
];

/** What a therapist actually gets: an example prep brief, with each line tied to a session. */
const ExampleBrief = () => {
  const cite = (label: string) => (
    <Chip size="small" variant="outlined" color="primary" label={label} sx={{ height: 22, fontSize: 12, ml: 0.75 }} />
  );
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2.5, sm: 3 }, borderRadius: 4 }} aria-label="Example session brief">
      <Typography variant="body2" color="text.secondary">Example brief, synthetic client</Typography>
      <Typography variant="h6" component="p" sx={{ mt: 0.5 }}>Jordan Ellis, Tuesday at 10:00 AM</Typography>
      <Stack spacing={1.75} mt={2}>
        <Typography>
          Anxiety is easing: GAD-7 went from 14 at intake to 9 last week.{cite("Intake, Oct 4")}{cite("Screening, Oct 25")}
        </Typography>
        <Typography>
          Spoke up in a team meeting at 6/10 anxiety instead of the expected 9/10.{cite("Session, Oct 25")}
        </Typography>
        <Box sx={{ pl: 1.5, borderLeft: 3, borderColor: "warning.main" }}>
          <Typography>
            Still open: sleep is around 6 hours, with rumination on Sunday evenings.{cite("Session, Oct 18")}
          </Typography>
        </Box>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 2.5, pt: 2, borderTop: 1, borderColor: "divider" }}>
        Homework this week: thought records 4 of 7, worry time 5 of 7.
      </Typography>
    </Paper>
  );
};

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
      <Container maxWidth="lg" sx={{ pt: { xs: 6, md: 10 }, pb: { xs: 6, md: 9 } }}>
        <Box sx={{ display: "grid", gap: { xs: 5, md: 8 }, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, alignItems: "center" }}>
          <Box>
            <Typography variant="h2" component="h1" sx={{ fontSize: { xs: "2.4rem", md: "3.4rem" }, lineHeight: 1.08 }}>
              Every client's story, ready before the session
            </Typography>
            <Typography sx={{ mt: 3, fontSize: "1.125rem", color: "text.secondary", maxWidth: 520 }}>
              TherapyBot turns your notes, transcripts and screenings into a record you can ask questions of. Prep in
              minutes, draft notes from transcripts, and keep clients supported between sessions.
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mt: 4 }}>
              <LinkButton to="/therapists/register" variant="contained" size="large">Start as a therapist</LinkButton>
              <LinkButton to="/register" variant="outlined" size="large">I'm looking for support</LinkButton>
            </Stack>
          </Box>
          <ExampleBrief />
        </Box>
      </Container>

      <Box sx={{ bgcolor: "background.paper", borderTop: 1, borderBottom: 1, borderColor: "divider" }}>
        <Container maxWidth="lg" sx={{ py: { xs: 6, md: 8 } }}>
          <Typography variant="h4" component="h2" mb={4}>Where it fits in your week</Typography>
          <Box component="ol" sx={{ listStyle: "none", p: 0, m: 0, display: "grid", gap: { xs: 3, md: 4 },
                                    gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" } }}>
            {WEEK.map((step, i) => (
              <Box component="li" key={step.when} sx={{ pt: 2, borderTop: 2, borderColor: i === 0 ? "primary.main" : "divider" }}>
                <Typography variant="body2" color="primary" fontWeight={600}>Step {i + 1}</Typography>
                <Typography variant="h6" component="h3" sx={{ mt: 0.5 }}>{step.when}</Typography>
                <Typography color="text.secondary" sx={{ mt: 1 }}>{step.what}</Typography>
              </Box>
            ))}
          </Box>
        </Container>
      </Box>

      <Container maxWidth="lg" sx={{ py: { xs: 6, md: 8 } }}>
        <Box sx={{ display: "grid", gap: { xs: 3, md: 8 }, gridTemplateColumns: { xs: "1fr", md: "1fr 2fr" } }}>
          <Box>
            <Typography variant="h4" component="h2">Built for clinical trust</Typography>
            <Typography color="text.secondary" sx={{ mt: 1.5 }}>It supports your judgment. It doesn't replace it.</Typography>
          </Box>
          <Box component="dl" sx={{ m: 0, display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
            {TRUST.map((t) => (
              <Box key={t.term} sx={{ pt: 2, borderTop: 1, borderColor: "divider" }}>
                <Typography component="dt" fontWeight={600}>{t.term}</Typography>
                <Typography component="dd" color="text.secondary" sx={{ m: 0, mt: 0.75 }}>{t.detail}</Typography>
              </Box>
            ))}
          </Box>
        </Box>
      </Container>

      <Box sx={{ bgcolor: "background.paper", borderTop: 1, borderColor: "divider" }}>
        <Container maxWidth="lg" sx={{ py: { xs: 6, md: 8 } }}>
          <Box sx={{ display: "grid", gap: { xs: 3, md: 8 }, gridTemplateColumns: { xs: "1fr", md: "1fr 2fr" }, alignItems: "start" }}>
            <Typography variant="h4" component="h2">For clients</Typography>
            <Box>
              <Typography sx={{ fontSize: "1.125rem", maxWidth: 620 }}>
                If your therapist uses TherapyBot, the time between appointments follows the plan you made together:
                daily exercises with reminders, and a companion to talk things through. Not seeing anyone yet? Find
                licensed providers near you, with a script for the first call.
              </Typography>
              <LinkButton to="/register" variant="contained" sx={{ mt: 3 }}>Create a free account</LinkButton>
            </Box>
          </Box>
        </Container>
      </Box>
    </>
  );
};

export default Home;
