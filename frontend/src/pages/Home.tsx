import { Box, Typography, Button, Grid, Paper } from "@mui/material";
import { useNavigate } from "@tanstack/react-router";

export const Home = () => {
  const navigate = useNavigate();

  return (
    <Box sx={{ padding: 4 }}>
      {/* Hero Section */}
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
          mb: 6,
        }}
      >
        <Typography mt={4} variant="h2" component="h1" gutterBottom>
          Welcome to TherapyBot
        </Typography>
        <Typography variant="h5" color="textSecondary" gutterBottom>
          Your AI companion for mental wellness — here to listen, support, and
          guide you anytime.
        </Typography>
        <Box
          component="img"
          src="../src/assets/therapy.jpg"
          alt="Therapy illustration"
          sx={{ width: "100%", maxWidth: 400, mt: 3, borderRadius: 2 }}
        />
        <Typography variant="body1" sx={{ mt: 3, maxWidth: 600 }}>
          TherapyBot is an AI-powered tool designed to help you explore your
          thoughts and emotions in a safe, private environment. Whether you’re
          dealing with stress, anxiety, or just need someone to talk to,
          TherapyBot is here to provide guidance and support.
        </Typography>
        <Button
          variant="contained"
          color="primary"
          sx={{ mt: 4, px: 5 }}
          onClick={() => {
            navigate({ to: "/get-started" });
          }}
        >
          Start Chatting
        </Button>
      </Box>

      {/* How It Works Section */}
      <Box sx={{ mb: 6 }}>
        <Typography variant="h4" component="h2" gutterBottom textAlign="center">
          How It Works
        </Typography>
        <Grid container spacing={4} justifyContent="center">
          <Grid>
            <Paper sx={{ p: 3, textAlign: "center" }} elevation={3}>
              <Typography variant="h6" gutterBottom>
                Chat Anytime
              </Typography>
              <Typography variant="body2">
                Start a conversation and share what’s on your mind. TherapyBot
                is available 24/7.
              </Typography>
            </Paper>
          </Grid>
          <Grid>
            <Paper sx={{ p: 3, textAlign: "center" }} elevation={3}>
              <Typography variant="h6" gutterBottom>
                Personalized Guidance
              </Typography>
              <Typography variant="body2">
                Get AI-driven advice tailored to your feelings and situation.
              </Typography>
            </Paper>
          </Grid>
          <Grid>
            <Paper sx={{ p: 3, textAlign: "center" }} elevation={3}>
              <Typography variant="h6" gutterBottom>
                Privacy First
              </Typography>
              <Typography variant="body2">
                Your conversations are confidential and secure.
              </Typography>
            </Paper>
          </Grid>
        </Grid>
      </Box>

      {/* Optional Footer / Disclaimer */}
      <Box sx={{ textAlign: "center", mt: 6 }}>
        <Typography variant="caption" color="textSecondary">
          TherapyBot is not a replacement for professional therapy. If you are
          in crisis, please contact a licensed mental health professional.
        </Typography>
      </Box>
    </Box>
  );
};

export default Home;
