import { Box, Typography, Paper, Divider } from "@mui/material";
import { useUser } from "../context/UserContext";
import { TherapyForm } from "../components/TherapyForm";

export const GettingStarted = () => {
  const { user } = useUser();

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-start",
        minHeight: "80vh",
        padding: 4,
        backgroundColor: "#f5f5f5",
      }}
    >
      <Paper
        sx={{
          p: 5,
          maxWidth: 600,
          width: "100%",
          borderRadius: 3,
          boxShadow: 4,
          backgroundColor: "#ffffff",
        }}
      >
        {/* Greeting */}
        <Typography variant="h4" component="h1" gutterBottom>
          Hello, {user?.username ?? "Guest"}!
        </Typography>
        <Typography variant="body1" color="textSecondary" gutterBottom>
          You're in a safe space. Share what's on your mind and TherapyBot will
          provide thoughtful, evidence-based guidance to support you.
        </Typography>

        <Divider sx={{ my: 3 }} />

        {/* Form */}
        <TherapyForm />

        {/* Optional note */}
        <Typography
          variant="caption"
          color="textSecondary"
          sx={{ mt: 3, display: "block", textAlign: "center" }}
        >
          Your responses are private and confidential.
        </Typography>
      </Paper>
    </Box>
  );
};
