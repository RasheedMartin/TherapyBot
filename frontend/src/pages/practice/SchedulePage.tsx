import { Container, Stack, Typography } from "@mui/material";
import { SyntheticDataBanner } from "../../components/practice/SyntheticDataBanner";
import { WeekSchedule } from "../../components/practice/WeekSchedule";

/** The therapist's week across clients, with scheduling and calendar sync. */
export const SchedulePage = () => (
  <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
    <Typography variant="h4" component="h1">Schedule</Typography>
    <Typography color="text.secondary" mb={3}>
      Your sessions across all clients. Subscribe once and they appear in your own calendar too.
    </Typography>
    <Stack spacing={3}>
      <SyntheticDataBanner />
      <WeekSchedule />
    </Stack>
  </Container>
);
