import { useEffect, useRef } from "react";
import { Alert, Button, CircularProgress, Stack, Typography } from "@mui/material";
import { CheckCircleOutline } from "@mui/icons-material";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearch } from "@tanstack/react-router";
import api, { getErrorMessage } from "../api/client";
import { AuthLayout } from "../components/AuthLayout";
import { LinkButton } from "../components/RouterLink";
import { useAuth } from "../context/AuthContext";

interface CheckInInfo {
  step: string;
  plan: string;
  date: string;
  done: boolean;
}

const formatDay = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });

/**
 * Opened from a reminder email's "Mark done" link. Confirming takes one tap; the link itself
 * changes nothing, because email security scanners open links automatically.
 */
export const QuickCheckInPage = () => {
  const { t } = useSearch({ from: "/check-in" });
  const { authenticated } = useAuth();
  const info = useQuery({
    queryKey: ["quick-check-in", t],
    queryFn: async () => (await api.get<CheckInInfo>("quick-check-in/", { params: { t } })).data,
    enabled: !!t,
    retry: false,
  });
  const confirm = useMutation({
    mutationFn: async () => (await api.post<CheckInInfo>("quick-check-in/", { t })).data,
  });
  const done = confirm.data?.done ?? info.data?.done;

  return (
    <AuthLayout title={done ? "Nice work" : "Check in"}>
      <Stack spacing={2.5} alignItems="stretch" textAlign="center">
        {info.isLoading && <CircularProgress sx={{ alignSelf: "center" }} />}
        {(info.isError || !t) && <Alert severity="warning">{getErrorMessage(info.error, "This link is incomplete.")}</Alert>}
        {info.data && (
          <>
            {done && <CheckCircleOutline color="primary" sx={{ fontSize: 56, alignSelf: "center" }} />}
            <Typography variant="h6">{info.data.step}</Typography>
            <Typography color="text.secondary">
              {info.data.plan}, {formatDay(info.data.date)}
            </Typography>
            {done ? (
              <Typography>Marked as done. Every small step counts.</Typography>
            ) : (
              <Button variant="contained" size="large" onClick={() => confirm.mutate()} disabled={confirm.isPending}>
                {confirm.isPending ? "Saving…" : "Mark as done"}
              </Button>
            )}
            {confirm.isError && <Alert severity="error">{getErrorMessage(confirm.error)}</Alert>}
          </>
        )}
        <LinkButton to={authenticated ? "/plans" : "/login"} variant={done ? "contained" : "text"}>
          {authenticated ? "See all of today's steps" : "Sign in to TherapyBot"}
        </LinkButton>
      </Stack>
    </AuthLayout>
  );
};

/** Opened from the "Stop daily reminders" link. */
export const RemindersOffPage = () => {
  const { t } = useSearch({ from: "/reminders/off" });
  const off = useMutation({ mutationFn: () => api.post("reminders/unsubscribe/", { t }) });
  const submitted = useRef(false);

  useEffect(() => {
    if (t && !submitted.current) {
      submitted.current = true;
      off.mutate();
    }
  }, [t, off]);

  return (
    <AuthLayout title="Daily reminders">
      <Stack spacing={2.5}>
        {off.isPending && <CircularProgress sx={{ alignSelf: "center" }} />}
        {off.isSuccess && <Alert severity="success">You won't get daily reminder emails anymore.</Alert>}
        {(off.isError || !t) && <Alert severity="error">{getErrorMessage(off.error, "This link isn't valid.")}</Alert>}
        <Typography variant="body2" color="text.secondary" textAlign="center">
          Changed your mind? You can turn reminders back on and pick a different time in your profile.
        </Typography>
        <LinkButton to="/profile" variant="outlined">
          Reminder settings
        </LinkButton>
      </Stack>
    </AuthLayout>
  );
};
