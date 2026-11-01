import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Collapse,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import {
  ChatBubbleOutline,
  ChecklistRtl,
  ContentCopy,
  DeleteOutline,
  DescriptionOutlined,
  ExpandMore,
  UploadFileOutlined,
} from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import api, { getErrorMessage, getFieldErrors } from "../api/client";
import type { Conversation, PlanDraft, SessionNote, SessionNoteSummary } from "../api/types";
import { PlanEditor } from "../components/plans/PlanEditor";
import { describeSchedule } from "../components/plans/schedule";
import { LinkButton } from "../components/RouterLink";

const formatDate = (iso: string | null) =>
  iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }) : "";

const Section = ({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) => (
  <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4 }}>
    <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1.5} spacing={1}>
      <Typography variant="h6" component="h2">
        {title}
      </Typography>
      {action}
    </Stack>
    {children}
  </Paper>
);

const NewNoteForm = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"paste" | "upload">("paste");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [sessionDate, setSessionDate] = useState("");

  const create = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      if (mode === "upload" && file) form.append("file", file);
      else form.append("text", text);
      if (title.trim()) form.append("title", title.trim());
      if (sessionDate) form.append("session_date", sessionDate);
      return (await api.post<SessionNote>("notes/", form, { headers: { "Content-Type": "multipart/form-data" } })).data;
    },
    onSuccess: (note) => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      queryClient.setQueryData(["note", note.id], note);
      navigate({ to: "/notes/$noteId", params: { noteId: String(note.id) } });
    },
  });
  const errors = getFieldErrors(create.error);
  const ready = mode === "paste" ? text.trim().length >= 20 : !!file;

  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4 }}>
      <Typography variant="h6" component="h2">
        Understand your session notes
      </Typography>
      <Typography color="text.secondary" mb={2}>
        Paste notes or an after-visit summary from your therapist or doctor. We'll explain it in plain language and help
        you turn homework into a plan.
      </Typography>
      <Tabs value={mode} onChange={(_, v) => setMode(v)} sx={{ mb: 2 }}>
        <Tab value="paste" label="Paste text" />
        <Tab value="upload" label="Upload file" />
      </Tabs>
      <Box
        component="form"
        onSubmit={(e) => {
          e.preventDefault();
          if (ready) create.mutate();
        }}
      >
        <Stack spacing={2}>
          {mode === "paste" ? (
            <TextField
              multiline
              minRows={6}
              maxRows={16}
              placeholder="e.g. Pt reports elevated anxiety re: work. Introduced thought record. HW: complete 1x/day…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              error={!!errors.text}
              helperText={errors.text ?? `${text.length.toLocaleString()} / 20,000 characters`}
            />
          ) : (
            <Box>
              <Button component="label" variant="outlined" startIcon={<UploadFileOutlined />}>
                {file ? file.name : "Choose a PDF, Word or text file"}
                <input hidden type="file" accept=".pdf,.docx,.txt,.md" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              </Button>
              <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                Patient-portal PDFs work well. Scanned images can't be read yet, so paste the text instead.
              </Typography>
              {errors.file && (
                <Alert severity="warning" sx={{ mt: 1.5 }}>
                  {errors.file}
                </Alert>
              )}
            </Box>
          )}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField size="small" label="Title (optional)" value={title} onChange={(e) => setTitle(e.target.value)} />
            <TextField
              size="small"
              type="date"
              label="Session date (optional)"
              value={sessionDate}
              onChange={(e) => setSessionDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Stack>
          {create.isError && !Object.keys(errors).length && <Alert severity="error">{getErrorMessage(create.error)}</Alert>}
          <Stack direction="row" spacing={2} alignItems="center">
            <Button type="submit" variant="contained" disabled={!ready || create.isPending} startIcon={create.isPending ? <CircularProgress size={16} color="inherit" /> : undefined}>
              {create.isPending ? "Reading your notes…" : "Explain my notes"}
            </Button>
            <Typography variant="caption" color="text.secondary">
              Private to you. Notes are sent to our AI provider only to create the explanation.
            </Typography>
          </Stack>
        </Stack>
      </Box>
    </Paper>
  );
};

export const NotesPage = () => {
  const navigate = useNavigate();
  const notes = useQuery({
    queryKey: ["notes"],
    queryFn: async () => (await api.get<SessionNoteSummary[]>("notes/")).data,
  });

  return (
    <Container maxWidth="md" sx={{ py: { xs: 3, md: 6 } }}>
      <Typography variant="h4" component="h1">
        Session notes
      </Typography>
      <Typography color="text.secondary" mb={3}>
        Make sense of what your clinician wrote, and carry it into your week.
      </Typography>
      <Stack spacing={3}>
        <NewNoteForm />
        {!!notes.data?.length && (
          <Paper variant="outlined" sx={{ borderRadius: 4 }}>
            <List disablePadding>
              {notes.data.map((n) => (
                <ListItemButton
                  key={n.id}
                  onClick={() => navigate({ to: "/notes/$noteId", params: { noteId: String(n.id) } })}
                  sx={{ py: 1.5 }}
                >
                  <DescriptionOutlined color="primary" sx={{ mr: 2 }} />
                  <ListItemText
                    primary={n.title}
                    secondary={n.session_date ? `Session on ${formatDate(n.session_date)}` : `Added ${formatDate(n.created_at)}`}
                    slotProps={{ primary: { fontWeight: 500 } }}
                  />
                </ListItemButton>
              ))}
            </List>
          </Paper>
        )}
      </Stack>
    </Container>
  );
};

export const NoteDetailPage = () => {
  const { noteId } = useParams({ from: "/notes/$noteId" });
  const id = Number(noteId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showOriginal, setShowOriginal] = useState(false);
  const [planDraft, setPlanDraft] = useState<PlanDraft | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const note = useQuery({
    queryKey: ["note", id],
    queryFn: async () => (await api.get<SessionNote>(`notes/${id}/`)).data,
  });
  const discuss = useMutation({
    mutationFn: async () => (await api.post<Conversation>(`notes/${id}/discuss/`)).data,
    onSuccess: (conversation) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      navigate({ to: "/chat", search: { c: conversation.id } });
    },
  });
  const remove = useMutation({
    mutationFn: () => api.delete(`notes/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      navigate({ to: "/notes" });
    },
  });

  if (note.isLoading)
    return (
      <Box sx={{ display: "grid", placeItems: "center", py: 10 }}>
        <CircularProgress />
      </Box>
    );
  if (note.isError || !note.data)
    return (
      <Container maxWidth="md" sx={{ py: 6 }}>
        <Alert severity="warning">{getErrorMessage(note.error, "These notes couldn't be found.")}</Alert>
      </Container>
    );

  const n = note.data;
  const e = n.explanation;

  return (
    <Container maxWidth="md" sx={{ py: { xs: 3, md: 6 } }}>
      <LinkButton to="/notes" size="small" sx={{ mb: 1, ml: -1 }}>
        ← All notes
      </LinkButton>
      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" spacing={2} mb={3}>
        <Box>
          <Typography variant="h4" component="h1">
            {n.title}
          </Typography>
          <Typography color="text.secondary">
            {n.session_date ? `Session on ${formatDate(n.session_date)}` : `Added ${formatDate(n.created_at)}`}
          </Typography>
        </Box>
        <Button color="error" startIcon={<DeleteOutline />} onClick={() => setConfirmDelete(true)} sx={{ flexShrink: 0 }}>
          Delete
        </Button>
      </Stack>

      <Stack spacing={3}>
        <Section title="In plain language">
          <Typography>{e.summary}</Typography>
          {!!e.key_points?.length && (
            <Box component="ul" sx={{ pl: 2.5, mb: 0, mt: 1.5, "& li": { mb: 0.5 } }}>
              {e.key_points.map((p) => (
                <li key={p}>
                  <Typography>{p}</Typography>
                </li>
              ))}
            </Box>
          )}
        </Section>

        {/* What to do next: the explanation hands off to plans and chat */}
        <Paper sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4, bgcolor: "primary.main", color: "primary.contrastText" }}>
          <Typography variant="h6" component="h2" mb={1.5}>
            What would help next?
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            {!!e.homework?.length && (
              <Button
                variant="contained"
                color="inherit"
                sx={{ color: "primary.main" }}
                startIcon={<ChecklistRtl />}
                onClick={() =>
                  setPlanDraft({
                    title: `Homework: ${n.title}`.slice(0, 120),
                    summary: "From my session notes.",
                    conversation: null,
                    steps: e.homework,
                  })
                }
              >
                Turn homework into a plan
              </Button>
            )}
            <Button
              variant="outlined"
              color="inherit"
              startIcon={discuss.isPending ? <CircularProgress size={16} color="inherit" /> : <ChatBubbleOutline />}
              onClick={() => discuss.mutate()}
              disabled={discuss.isPending}
            >
              Talk it through
            </Button>
          </Stack>
        </Paper>

        {!!e.homework?.length && (
          <Section title="Your homework">
            <Stack spacing={1.5}>
              {e.homework.map((h) => (
                <Box key={h.title}>
                  <Typography fontWeight={500}>{h.title}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {describeSchedule(h)}
                    {h.details && ` · ${h.details}`}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Section>
        )}

        {!!e.terms?.length && (
          <Section title="Terms explained">
            <Stack spacing={1.5}>
              {e.terms.map((t) => (
                <Box key={t.term}>
                  <Typography fontWeight={600}>{t.term}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {t.meaning}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Section>
        )}

        {!!e.questions?.length && (
          <Section
            title="Questions for your next session"
            action={
              <Button
                size="small"
                startIcon={<ContentCopy fontSize="small" />}
                onClick={() => {
                  navigator.clipboard?.writeText(e.questions.map((q) => `• ${q}`).join("\n"));
                  setCopied(true);
                }}
              >
                {copied ? "Copied" : "Copy"}
              </Button>
            }
          >
            <Box component="ul" sx={{ pl: 2.5, my: 0, "& li": { mb: 0.75 } }}>
              {e.questions.map((q) => (
                <li key={q}>
                  <Typography>{q}</Typography>
                </li>
              ))}
            </Box>
          </Section>
        )}

        <Box>
          <Button
            color="inherit"
            onClick={() => setShowOriginal((v) => !v)}
            endIcon={<ExpandMore sx={{ transform: showOriginal ? "rotate(180deg)" : "none", transition: "transform .2s" }} />}
          >
            Original notes
          </Button>
          <Collapse in={showOriginal}>
            <Paper variant="outlined" sx={{ p: 2, mt: 1, borderRadius: 3, whiteSpace: "pre-wrap", fontFamily: "monospace", fontSize: 13 }}>
              {n.original_text}
            </Paper>
          </Collapse>
        </Box>

        <Typography variant="caption" color="text.secondary">
          This explanation is AI-generated and may miss nuance. Your clinician is the best source on what your notes mean;
          bring any questions to your next session.
        </Typography>
      </Stack>

      <PlanEditor
        open={!!planDraft}
        initial={planDraft}
        heading="Plan from your homework"
        onClose={() => setPlanDraft(null)}
        onSaved={() => {
          setPlanDraft(null);
          navigate({ to: "/plans" });
        }}
      />
      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)}>
        <DialogTitle>Delete these notes?</DialogTitle>
        <DialogContent>
          <DialogContentText>The notes and their explanation will be permanently deleted. Plans you made from them stay.</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(false)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={() => remove.mutate()}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};
