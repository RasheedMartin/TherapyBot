import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import type { MyCheckIn } from "../../api/types";
import { ScreeningQuestions } from "../screenings/ScreeningQuestions";
import { MY_CHECKINS_KEY, useMyCheckIns } from "./useMyCheckIns";

/** Fill in a check-in. Afterwards: thanks, or crisis support if a safety answer was flagged. */
export const CompleteCheckInDialog = ({ checkIn, onClose }: { checkIn: MyCheckIn | null; onClose: () => void }) => {
  const queryClient = useQueryClient();
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const instrument = checkIn?.instrument;
  const complete = instrument && instrument.items.every((_, i) => answers[i] != null);

  const submit = useMutation({
    mutationFn: async (c: MyCheckIn) =>
      (await api.post<{ flagged: boolean; support_message?: string }>("screenings/mine/", {
        assignment: c.id,
        responses: c.instrument.items.map((_, i) => answers[i]),
      })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MY_CHECKINS_KEY }),
  });
  const close = () => {
    setAnswers({});
    submit.reset();
    onClose();
  };

  return (
    <Dialog open={!!checkIn} onClose={close} maxWidth="md" fullWidth>
      <DialogTitle>{instrument?.name}</DialogTitle>
      <DialogContent dividers>
        {submit.isSuccess ? (
          submit.data.flagged ? (
            <Alert severity="warning">
              <Typography fontWeight={600} mb={0.5}>Thank you for answering honestly.</Typography>
              {submit.data.support_message}
            </Alert>
          ) : (
            <Typography>Thanks. {checkIn?.therapist_name} will see your answers before your next session.</Typography>
          )
        ) : (
          <>
            {checkIn?.note && (
              <Alert severity="info" icon={false} sx={{ mb: 2 }}>
                {checkIn.therapist_name}: {checkIn.note}
              </Alert>
            )}
            {instrument && (
              <ScreeningQuestions instrument={instrument} answers={answers}
                                  onAnswer={(i, v) => setAnswers((a) => ({ ...a, [i]: v }))} />
            )}
            {submit.isError && <Alert severity="error" sx={{ mt: 2 }}>{getErrorMessage(submit.error)}</Alert>}
          </>
        )}
      </DialogContent>
      <DialogActions>
        {submit.isSuccess ? (
          <Button variant="contained" onClick={close}>Done</Button>
        ) : (
          <>
            <Button onClick={close}>Later</Button>
            <Button variant="contained" disabled={!complete || submit.isPending} onClick={() => checkIn && submit.mutate(checkIn)}>
              Send to {checkIn?.therapist_name.split(",")[0]}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
};

/** Check-ins the client's therapist sent that are open now. Hidden when there are none. */
export const CheckInsCard = () => {
  const checkIns = useMyCheckIns();
  const [open, setOpen] = useState<MyCheckIn | null>(null);
  const due = checkIns.data?.filter((c) => c.due) ?? [];
  if (!due.length && !open) return null;

  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4, borderColor: "primary.main" }}>
      <Typography variant="h6" component="h2">
        {due.length === 1 ? "A check-in from your therapist" : "Check-ins from your therapist"}
      </Typography>
      <Stack spacing={1.5} mt={1.5}>
        {due.map((c) => (
          <Stack key={c.id} direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
            <Box sx={{ flex: 1 }}>
              <Typography fontWeight={600}>{c.instrument.name}</Typography>
              <Typography variant="body2" color="text.secondary">
                {c.instrument.items.length} question{c.instrument.items.length === 1 ? "" : "s"} from {c.therapist_name}
              </Typography>
            </Box>
            <Button variant="contained" onClick={() => setOpen(c)} sx={{ alignSelf: { xs: "flex-start", sm: "center" } }}>
              Start
            </Button>
          </Stack>
        ))}
      </Stack>
      <CompleteCheckInDialog checkIn={open} onClose={() => setOpen(null)} />
    </Paper>
  );
};
