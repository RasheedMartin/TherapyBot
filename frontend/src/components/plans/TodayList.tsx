import { Alert, Box, Button, Checkbox, Chip, Paper, Stack, Tooltip, Typography } from "@mui/material";
import { LocalFireDepartment, PersonSearchOutlined } from "@mui/icons-material";
import { useNavigate } from "@tanstack/react-router";
import type { Plan } from "../../api/types";
import { describeSchedule, isDoneOn, isDueOn, streak } from "./schedule";
import { useCheckIn } from "./useCheckIn";

export /** Jumps from a "contact a therapist" step to the Find care shortlist. */
const ShortlistButton = ({ label, outlined }: { label: string; outlined?: boolean }) => {
  const navigate = useNavigate();
  return (
    <Button
      size="small"
      variant={outlined ? "outlined" : "text"}
      startIcon={outlined ? <PersonSearchOutlined /> : undefined}
      onClick={() => navigate({ to: "/find-care", search: { tab: "shortlist" } })}
    >
      {label}
    </Button>
  );
};

/** Every step due today across the user's active plans, as one checklist. */
export const TodayList = ({ plans }: { plans: Plan[] }) => {
  const checkIn = useCheckIn();
  const today = new Date();
  const due = plans.flatMap((plan) =>
    plan.steps.filter((s) => isDueOn(s, today)).map((step) => ({ plan, step })),
  );
  due.sort((a, b) => (a.step.time_of_day ?? "99").localeCompare(b.step.time_of_day ?? "99"));
  const doneCount = due.filter(({ step }) => isDoneOn(step, today)).length;

  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4 }}>
      <Stack direction="row" alignItems="baseline" justifyContent="space-between" mb={1}>
        <Typography variant="h6" component="h2">
          Today
        </Typography>
        {due.length > 0 && (
          <Typography variant="body2" color="text.secondary">
            {doneCount} of {due.length} done
          </Typography>
        )}
      </Stack>
      {due.length === 0 && <Typography color="text.secondary">Nothing scheduled for today. Rest counts too.</Typography>}
      {due.length > 0 && doneCount === due.length && (
        <Alert severity="success" sx={{ mb: 1 }}>
          You did everything you planned today. That's worth noticing.
        </Alert>
      )}
      <Stack>
        {due.map(({ plan, step }) => {
          const done = isDoneOn(step, today);
          const days = streak(step, today);
          return (
            <Stack key={step.id} direction="row" alignItems="center" spacing={1} sx={{ py: 0.5 }}>
              <Checkbox
                checked={done}
                onChange={(e) => checkIn.mutate({ step, day: today, done: e.target.checked })}
                inputProps={{ "aria-label": step.title }}
              />
              <Box flex={1} minWidth={0}>
                <Typography sx={{ textDecoration: done ? "line-through" : "none", color: done ? "text.secondary" : "text.primary" }}>
                  {step.title}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {plan.title} · {describeSchedule(step)}
                </Typography>
              </Box>
              {step.action === "find_care" && !done && (
                <ShortlistButton label="Shortlist" />
              )}
              {days >= 2 && (
                <Tooltip title={`${days}-day streak`}>
                  <Chip size="small" icon={<LocalFireDepartment />} label={days} color="secondary" variant="outlined" />
                </Tooltip>
              )}
            </Stack>
          );
        })}
      </Stack>
    </Paper>
  );
};

