import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  InputAdornment,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { AutoAwesomeOutlined, Send } from "@mui/icons-material";
import { useMutation } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import type { RecordAnswer, SessionPrep } from "../../api/types";
import { CitedList, CitedText } from "./Citations";
import { formatDate } from "./format";

export const Panel = ({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) => (
  <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4 }}>
    <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2} spacing={1}>
      <Typography variant="h6" component="h2">
        {title}
      </Typography>
      {action}
    </Stack>
    {children}
  </Paper>
);

const AiLabel = () => (
  <Typography variant="caption" color="text.secondary" display="block" mt={2}>
    AI-generated from this client's record. Every point links to the session it came from; check before relying on it.
  </Typography>
);

/** "What did we work on, what's open, did they do the homework?" Facts from the database, synthesis cited. */
export const PrepPanel = ({ clientId }: { clientId: number }) => {
  const prep = useMutation({
    mutationFn: async () => (await api.post<SessionPrep>(`practice/clients/${clientId}/prep/`)).data,
  });
  const data = prep.data;
  const facts = data?.facts;

  return (
    <Panel
      title="Prep for next session"
      action={
        <Button
          variant={data ? "outlined" : "contained"}
          startIcon={prep.isPending ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeOutlined />}
          onClick={() => prep.mutate()}
          disabled={prep.isPending}
        >
          {prep.isPending ? "Reading the record…" : data ? "Refresh" : "Prepare"}
        </Button>
      }
    >
      {!data && !prep.isPending && (
        <Typography color="text.secondary">
          Summarizes the last few sessions, open threads, homework and score changes, with every point linked to its
          source.
        </Typography>
      )}
      {prep.isError && <Alert severity="error">{getErrorMessage(prep.error)}</Alert>}
      {facts && data && (
        <Stack spacing={2.5}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip label={`${facts.sessions_completed} sessions`} />
            <Chip label={`Last: ${formatDate(facts.last_session_date)}`} />
            {facts.next_session_date && <Chip color="primary" variant="outlined" label={`Next: ${formatDate(facts.next_session_date)}`} />}
            {facts.screenings.map((s) => (
              <Chip
                key={s.instrument}
                variant="outlined"
                label={`${s.instrument} ${s.latest_total} (${s.latest_severity})${s.change != null ? ` ${s.change > 0 ? "+" : ""}${s.change}` : ""}`}
              />
            ))}
            {facts.open_risk_flags > 0 && <Chip color="warning" label={`${facts.open_risk_flags} open safety flag(s)`} />}
          </Stack>
          {data.summary && <CitedText text={data.summary} sources={data.sources} clientId={clientId} />}
          <CitedList title="Last session" items={data.last_session} sources={data.sources} clientId={clientId} />
          <CitedList title="Open threads" items={data.open_threads} sources={data.sources} clientId={clientId} />
          {facts.homework.length > 0 && (
            <Box>
              <Typography variant="overline" color="text.secondary">Homework (last 14 days)</Typography>
              {facts.homework.map((h) => (
                <Typography key={h.step}>
                  {h.step}:{" "}
                  {h.due_last_14_days != null ? `${h.done_last_14_days} of ${h.due_last_14_days} done` : "completion not shared by the client"}
                </Typography>
              ))}
            </Box>
          )}
          <CitedList title="Suggested focus" items={data.suggested_focus} sources={data.sources} clientId={clientId} />
          {!data.summary && data.sources.length === 0 && (
            <Typography color="text.secondary">There are no notes in the record yet.</Typography>
          )}
          <AiLabel />
        </Stack>
      )}
    </Panel>
  );
};

/** Free-form questions answered strictly from this client's record. */
export const AskPanel = ({ clientId }: { clientId: number }) => {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<{ question: string; answer: RecordAnswer }[]>([]);
  const ask = useMutation({
    mutationFn: async (q: string) => (await api.post<RecordAnswer>(`practice/clients/${clientId}/ask/`, { question: q })).data,
    onSuccess: (answer, q) => {
      setHistory((h) => [{ question: q, answer }, ...h].slice(0, 5));
      setQuestion("");
    },
  });

  return (
    <Panel title="Ask the record">
      <Box component="form" onSubmit={(e) => { e.preventDefault(); if (question.trim()) ask.mutate(question.trim()); }}>
        <TextField
          placeholder="e.g. What homework did we assign, and is it working?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={ask.isPending}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton type="submit" disabled={!question.trim() || ask.isPending} aria-label="Ask">
                  {ask.isPending ? <CircularProgress size={20} /> : <Send />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
      </Box>
      {ask.isError && <Alert severity="error" sx={{ mt: 2 }}>{getErrorMessage(ask.error)}</Alert>}
      <Stack spacing={2.5} mt={history.length ? 2.5 : 0}>
        {history.map(({ question: q, answer }, i) => (
          <Box key={i}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              {q}
            </Typography>
            <CitedText text={answer.answer} sources={answer.sources} clientId={clientId} />
          </Box>
        ))}
      </Stack>
      {history.length > 0 && <AiLabel />}
    </Panel>
  );
};
