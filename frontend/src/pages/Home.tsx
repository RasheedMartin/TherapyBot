import { Box, Button, Container, Paper, Stack, Typography } from "@mui/material";
import { ChatBubbleOutline, Lock, Psychology, Schedule } from "@mui/icons-material";
import { Link } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";
import { RequireAuth } from "../components/RouteGuards";
import { Dashboard } from "./Dashboard";

const FEATURES = [
  {
    icon: <Schedule />,
    title: "There when you need it",
    body: "Talk through what's on your mind any time of day, at your own pace.",
  },
  {
    icon: <Psychology />,
    title: "Grounded in evidence",
    body: "Guidance draws on approaches like CBT and DBT, and on trusted mental-health resources.",
  },
  {
    icon: <ChatBubbleOutline />,
    title: "Conversations that remember",
    body: "Pick up where you left off. Each conversation keeps its own history and focus.",
  },
  {
    icon: <Lock />,
    title: "Private to you",
    body: "Your conversations are tied to your account and never shared with other users.",
  },
];

export const Home = () => {
  const { authenticated } = useAuth();

  // Signed-in users get their hub instead of the marketing page
  if (authenticated) {
    return (
      <RequireAuth verified>
        <Dashboard />
      </RequireAuth>
    );
  }

  return (
    <>
      <Box
        sx={(theme) => ({
          background: `radial-gradient(ellipse at top, ${theme.vars?.palette.primary.main ?? theme.palette.primary.main}22, transparent 60%)`,
        })}
      >
        <Container maxWidth="md" sx={{ py: { xs: 8, md: 12 }, textAlign: "center" }}>
          <Typography variant="overline" color="primary" fontWeight={700} letterSpacing={2}>
            AI-powered emotional support
          </Typography>
          <Typography variant="h2" component="h1" sx={{ fontSize: { xs: "2.4rem", md: "3.5rem" }, mt: 1 }}>
            A calm space to talk things through
          </Typography>
          <Typography
            variant="h6"
            color="text.secondary"
            fontWeight={400}
            sx={{ mt: 3, maxWidth: 620, mx: "auto" }}
          >
            TherapyBot listens without judgment and offers practical, evidence-based ideas for handling stress,
            anxiety, relationships, and everyday challenges.
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} justifyContent="center" sx={{ mt: 5 }}>
            <Button component={Link} to={authenticated ? "/chat" : "/register"} variant="contained" size="large">
              {authenticated ? "Continue chatting" : "Start a conversation"}
            </Button>
            {!authenticated && (
              <Button component={Link} to="/login" variant="outlined" size="large">
                I already have an account
              </Button>
            )}
          </Stack>
        </Container>
      </Box>

      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 8 } }}>
        <Box
          sx={{
            display: "grid",
            gap: 3,
            gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" },
          }}
        >
          {FEATURES.map((f) => (
            <Paper key={f.title} variant="outlined" sx={{ p: 3, borderRadius: 4 }}>
              <Box
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: 3,
                  display: "grid",
                  placeItems: "center",
                  bgcolor: "action.hover",
                  color: "primary.main",
                  mb: 2,
                }}
              >
                {f.icon}
              </Box>
              <Typography variant="h6" gutterBottom>
                {f.title}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {f.body}
              </Typography>
            </Paper>
          ))}
        </Box>
      </Container>
    </>
  );
};

export default Home;
