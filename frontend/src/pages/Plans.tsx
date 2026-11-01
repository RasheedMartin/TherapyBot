import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  Add,
  ArchiveOutlined,
  CalendarMonthOutlined,
  DeleteOutline,
  EditOutlined,
  ExpandMore,
  MoreVert,
  SyncOutlined,
  UnarchiveOutlined,
} from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import api, { getErrorMessage } from "../api/client";
import type { Plan, PlanStep } from "../api/types";
import { CalendarSyncDialog } from "../components/plans/CalendarSyncDialog";
import { ReminderNudge } from "../components/plans/ReminderSettings";
import { ShortlistButton, TodayList } from "../components/plans/TodayList";
import { PLANS_KEY, useCheckIn } from "../components/plans/useCheckIn";
import { PlanEditor } from "../components/plans/PlanEditor";
import { addDays, describeSchedule, isDoneOn, isDueOn, isoDate } from "../components/plans/schedule";

const WeekDots = ({ step }: { step: PlanStep }) => {
  const checkIn = useCheckIn();
  const today = new Date();
  const days = Array.from({ length: 7 }, (_, i) => addDays(today, i - 6));
  return (
    <Stack direction="row" spacing={0.5}>
      {days.map((day) => {
        const due = isDueOn(step, day);
        const done = isDoneOn(step, day);
        const label = day.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
        return (
          <Tooltip key={isoDate(day)} title={`${label}: ${done ? "done" : due ? "not done" : "not scheduled"}`}>
            <Box
              component="button"
              type="button"
              aria-label={`${label}, ${done ? "done" : "not done"}`}
              onClick={() => checkIn.mutate({ step, day, done: !done })}
              sx={{
                width: 22,
                height: 22,
                p: 0,
                borderRadius: "50%",
                cursor: "pointer",
                border: 2,
                borderColor: done ? "primary.main" : due ? "divider" : "transparent",
                bgcolor: done ? "primary.main" : due ? "transparent" : "action.hover",
                color: done ? "primary.contrastText" : "text.secondary",
                fontSize: 10,
                fontFamily: "inherit",
                outline: isoDate(day) === isoDate(today) ? "2px solid" : "none",
                outlineColor: "secondary.main",
                outlineOffset: 1,
              }}
            >
              {day.toLocaleDateString([], { weekday: "narrow" })}
            </Box>
          </Tooltip>
        );
      })}
    </Stack>
  );
};

const PlanCard = ({ plan, onEdit }: { plan: Plan; onEdit: () => void }) => {
  const queryClient = useQueryClient();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: PLANS_KEY });
  const archive = useMutation({
    mutationFn: () => api.patch(`plans/${plan.id}/`, { archived: !plan.archived }),
    onSuccess: invalidate,
  });
  const remove = useMutation({ mutationFn: () => api.delete(`plans/${plan.id}/`), onSuccess: invalidate });
  const calendar = useMutation({
    mutationFn: async () => {
      const res = await api.get(`plans/${plan.id}/calendar.ics`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${plan.title.replace(/[^\w\s-]/g, "").trim() || "plan"}.ics`;
      link.click();
      URL.revokeObjectURL(url);
    },
  });

  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4, opacity: plan.archived ? 0.7 : 1 }}>
      <Stack direction="row" alignItems="flex-start" spacing={1}>
        <Box flex={1} minWidth={0}>
          <Typography variant="h6" component="h3">
            {plan.title}
          </Typography>
          {plan.summary && (
            <Typography variant="body2" color="text.secondary">
              {plan.summary}
            </Typography>
          )}
        </Box>
        <IconButton aria-label="Plan options" onClick={(e) => setAnchor(e.currentTarget)}>
          <MoreVert />
        </IconButton>
        <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)}>
          <MenuItem onClick={() => { setAnchor(null); onEdit(); }}>
            <ListItemIcon><EditOutlined fontSize="small" /></ListItemIcon>Edit
          </MenuItem>
          <MenuItem onClick={() => { setAnchor(null); calendar.mutate(); }}>
            <ListItemIcon><CalendarMonthOutlined fontSize="small" /></ListItemIcon>Add to calendar
          </MenuItem>
          <MenuItem onClick={() => { setAnchor(null); archive.mutate(); }}>
            <ListItemIcon>{plan.archived ? <UnarchiveOutlined fontSize="small" /> : <ArchiveOutlined fontSize="small" />}</ListItemIcon>
            {plan.archived ? "Restore" : "Archive"}
          </MenuItem>
          <MenuItem onClick={() => { setAnchor(null); setConfirmDelete(true); }} sx={{ color: "error.main" }}>
            <ListItemIcon><DeleteOutline fontSize="small" color="error" /></ListItemIcon>Delete
          </MenuItem>
        </Menu>
      </Stack>

      <Stack spacing={2} mt={2}>
        {plan.steps.map((step) => (
          <Stack
            key={step.id}
            direction={{ xs: "column", sm: "row" }}
            spacing={1.5}
            alignItems={{ xs: "flex-start", sm: "center" }}
            justifyContent="space-between"
          >
            <Box minWidth={0}>
              <Typography fontWeight={500}>{step.title}</Typography>
              <Typography variant="caption" color="text.secondary">
                {describeSchedule(step)}
                {step.details && `. ${step.details}`}
              </Typography>
            </Box>
            {step.frequency === "once" ? (
              <Stack direction="row" spacing={1} alignItems="center">
                {step.action === "find_care" && !(step.check_ins ?? []).length && (
                  <ShortlistButton label="Open shortlist" outlined />
                )}
                <Chip
                  size="small"
                  label={(step.check_ins ?? []).length ? "Done" : "To do"}
                  color={(step.check_ins ?? []).length ? "primary" : "default"}
                />
              </Stack>
            ) : (
              <WeekDots step={step} />
            )}
          </Stack>
        ))}
      </Stack>
      {calendar.isError && <Alert severity="error" sx={{ mt: 2 }}>{getErrorMessage(calendar.error)}</Alert>}

      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)}>
        <DialogTitle>Delete “{plan.title}”?</DialogTitle>
        <DialogContent>
          <DialogContentText>This removes the plan and its check-in history. Archiving keeps the history instead.</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(false)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={() => remove.mutate()}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
};

export const PlansPage = () => {
  const [editing, setEditing] = useState<Plan | null>(null);
  const [creating, setCreating] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [syncOpen, setSyncOpen] = useState(false);
  const { data: plans, isLoading, error } = useQuery({
    queryKey: PLANS_KEY,
    queryFn: async () => (await api.get<Plan[]>("plans/")).data,
  });

  const active = plans?.filter((p) => !p.archived) ?? [];
  const archived = plans?.filter((p) => p.archived) ?? [];

  return (
    <Container maxWidth="md" sx={{ py: { xs: 3, md: 6 } }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={3} spacing={2}>
        <Box>
          <Typography variant="h4" component="h1">
            Your plans
          </Typography>
          <Typography color="text.secondary">Small, steady steps. Check them off as you go.</Typography>
        </Box>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ flexShrink: 0 }}>
          <Button variant="contained" startIcon={<Add />} onClick={() => setCreating(true)}>
            New plan
          </Button>
          {active.length > 0 && (
            <Button variant="outlined" startIcon={<SyncOutlined />} onClick={() => setSyncOpen(true)}>
              Sync calendar
            </Button>
          )}
        </Stack>
      </Stack>

      {isLoading && (
        <Box sx={{ display: "grid", placeItems: "center", py: 10 }}>
          <CircularProgress />
        </Box>
      )}
      {error && <Alert severity="error">{getErrorMessage(error)}</Alert>}

      {plans && active.length === 0 && (
        <Paper variant="outlined" sx={{ p: 4, borderRadius: 4, textAlign: "center" }}>
          <Typography variant="h6" gutterBottom>
            No plans yet
          </Typography>
          <Typography color="text.secondary" mb={3}>
            Talk something through in chat, then tap “Make a plan” to turn it into a routine. Or start one yourself.
          </Typography>
          <Stack direction="row" spacing={1.5} justifyContent="center">
            <Button component={Link} to="/chat" variant="outlined">
              Go to chat
            </Button>
            <Button variant="contained" onClick={() => setCreating(true)}>
              Start a plan
            </Button>
          </Stack>
        </Paper>
      )}

      {active.length > 0 && (
        <Stack spacing={3}>
          <ReminderNudge />
          <TodayList plans={active} />
          {active.map((plan) => (
            <PlanCard key={plan.id} plan={plan} onEdit={() => setEditing(plan)} />
          ))}
        </Stack>
      )}

      {archived.length > 0 && (
        <Box mt={4}>
          <Button
            onClick={() => setShowArchived((v) => !v)}
            endIcon={<ExpandMore sx={{ transform: showArchived ? "rotate(180deg)" : "none", transition: "transform .2s" }} />}
            color="inherit"
          >
            Archived ({archived.length})
          </Button>
          <Collapse in={showArchived}>
            <Stack spacing={2} mt={2}>
              {archived.map((plan) => (
                <PlanCard key={plan.id} plan={plan} onEdit={() => setEditing(plan)} />
              ))}
            </Stack>
          </Collapse>
        </Box>
      )}

      <CalendarSyncDialog open={syncOpen} onClose={() => setSyncOpen(false)} />
      <PlanEditor
        open={creating || !!editing}
        initial={editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
        onSaved={() => {
          setCreating(false);
          setEditing(null);
        }}
      />
    </Container>
  );
};
