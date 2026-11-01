import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import { Add, AutoAwesomeOutlined, EditNoteOutlined, UploadFileOutlined } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import api, { getErrorMessage } from "../../api/client";
import {
  MODALITIES,
  type ClinicalDocument,
  type Plan,
  type PracticeClient,
  type Profile,
  type Timeline,
} from "../../api/types";
import { AskPanel, Panel, PrepPanel } from "../../components/practice/AssistantPanels";
import { formatDate, formatTime } from "../../components/practice/format";
import { BetweenSessionsPanel } from "../../components/practice/BetweenSessionsPanel";
import { ImportRecordsDialog } from "../../components/practice/ImportRecordsDialog";
import { ScheduleSessionDialog } from "../../components/practice/ScheduleSessionDialog";
import { ScreeningsPanel } from "../../components/practice/ScreeningsPanel";
import { SyntheticDataBanner } from "../../components/practice/SyntheticDataBanner";
import { TreatmentPlanPanel } from "../../components/practice/TreatmentPlanPanel";
import { PlanEditor } from "../../components/plans/PlanEditor";
import { describeSchedule } from "../../components/plans/schedule";
import { LinkButton } from "../../components/RouterLink";

const DOC_LABELS: Record<string, string> = {
  progress_note: "Note", transcript: "Transcript", intake: "Intake", client_upload: "Client upload", other: "Document",
};

const NOTE_TEMPLATES = {
  soap: "## Subjective\n\n\n## Objective\n\n\n## Assessment\n\n\n## Plan\n",
  dap: "## Data\n\n\n## Assessment\n\n\n## Plan\n",
};

/** Notes describe a session that happened: the latest non-cancelled session on or before today. */
const latestPastSession = (sessions: Timeline["sessions"]) => {
  const today = new Date().toISOString().slice(0, 10);
  return sessions.find((s) => s.date <= today && s.status !== "cancelled");
};

const DraftFromTranscriptDialog = ({ clientId, sessions, open, onClose }: {
  clientId: number;
  sessions: Timeline["sessions"];
  open: boolean;
  onClose: () => void;
}) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [source, setSource] = useState("");
  const [format, setFormat] = useState<string>("soap");
  const [session, setSession] = useState<number | "">(latestPastSession(sessions)?.id ?? "");
  const [saveTranscript, setSaveTranscript] = useState(true);
  const draft = useMutation({
    mutationFn: async () =>
      (await api.post<{ document: ClinicalDocument; review_flags: string[] }>(`practice/clients/${clientId}/draft-note/`, {
        source_text: source, format, session: session || null, save_transcript: saveTranscript,
      })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["timeline", clientId] }),
  });
  const openDraft = () =>
    draft.data && navigate({ to: "/practice/clients/$clientId/documents/$docId", params: { clientId: String(clientId), docId: String(draft.data.document.id) } });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Draft a note from a transcript</DialogTitle>
      <DialogContent dividers>
        {!draft.data ? (
          <Stack spacing={2}>
            <Typography variant="body2" color="text.secondary">
              Paste a transcript or your rough notes. The draft uses only what's here, and you review and sign it. The
              text is sent to the AI provider to create the draft.
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <ToggleButtonGroup exclusive size="small" value={format} onChange={(_, v) => v && setFormat(v)}>
                <ToggleButton value="soap">SOAP</ToggleButton>
                <ToggleButton value="dap">DAP</ToggleButton>
              </ToggleButtonGroup>
              <TextField select size="small" label="Session" value={session} onChange={(e) => setSession(Number(e.target.value) || "")} sx={{ minWidth: 220 }}>
                <MenuItem value="">Not linked to a session</MenuItem>
                {sessions.map((s) => <MenuItem key={s.id} value={s.id}>{formatDate(s.date)} · {s.status}</MenuItem>)}
              </TextField>
            </Stack>
            <TextField multiline minRows={10} value={source} onChange={(e) => setSource(e.target.value)}
                       placeholder={"T: How did the week go?\nC: …"} />
            <FormControlLabel control={<Checkbox checked={saveTranscript} onChange={(e) => setSaveTranscript(e.target.checked)} />}
                              label="Save the transcript to the record" />
            {draft.isError && <Alert severity="error">{getErrorMessage(draft.error)}</Alert>}
          </Stack>
        ) : (
          <Stack spacing={2}>
            <Alert severity="success">Draft saved. It isn't part of the signed record until you review and sign it.</Alert>
            {draft.data.review_flags.length > 0 && (
              <Alert severity="warning">
                <strong>Check before signing:</strong>
                <Box component="ul" sx={{ pl: 2.5, my: 0.5 }}>{draft.data.review_flags.map((f) => <li key={f}>{f}</li>)}</Box>
              </Alert>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => { draft.reset(); onClose(); }}>{draft.data ? "Close" : "Cancel"}</Button>
        {draft.data ? (
          <Button variant="contained" onClick={openDraft}>Review draft</Button>
        ) : (
          <Button variant="contained" onClick={() => draft.mutate()} disabled={source.trim().length < 40 || draft.isPending}
                  startIcon={draft.isPending ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeOutlined />}>
            {draft.isPending ? "Drafting…" : "Draft note"}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

const HomeworkPanel = ({ clientId, hasAccount }: { clientId: number; hasAccount: boolean }) => {
  const queryClient = useQueryClient();
  const [assigning, setAssigning] = useState(false);
  const homework = useQuery({
    queryKey: ["homework", clientId],
    queryFn: async () => (await api.get<Plan[]>(`practice/clients/${clientId}/homework/`)).data,
  });
  return (
    <Panel title="Homework" action={<Button size="small" startIcon={<Add />} disabled={!hasAccount} onClick={() => setAssigning(true)}>Assign</Button>}>
      {!hasAccount && <Typography color="text.secondary" variant="body2">Available once the client accepts your invitation.</Typography>}
      {homework.data?.length === 0 && hasAccount && (
        <Typography color="text.secondary" variant="body2">
          Assign exercises; they appear in the client's Plans with reminders, and completion shows here if they share it.
        </Typography>
      )}
      <Stack spacing={1}>
        {homework.data?.map((plan) =>
          plan.steps.map((step) => (
            <Box key={step.id}>
              <Typography fontWeight={500}>{step.title}</Typography>
              <Typography variant="caption" color="text.secondary">{plan.title} · {describeSchedule(step)}</Typography>
            </Box>
          )),
        )}
      </Stack>
      <PlanEditor
        open={assigning}
        initial={null}
        heading="Assign homework"
        createUrl={`practice/clients/${clientId}/homework/`}
        onClose={() => setAssigning(false)}
        onSaved={() => { setAssigning(false); queryClient.invalidateQueries({ queryKey: ["homework", clientId] }); }}
      />
    </Panel>
  );
};

export const ClientDetail = () => {
  const { clientId } = useParams({ from: "/practice/clients/$clientId" });
  const id = Number(clientId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [drafting, setDrafting] = useState(false);
  const profile = useQuery({ queryKey: ["profile"], queryFn: async () => (await api.get<Profile>("profile/")).data });
  const [addingSession, setAddingSession] = useState(false);
  const [importing, setImporting] = useState(false);
  const client = useQuery({ queryKey: ["practice-client", id], queryFn: async () => (await api.get<PracticeClient>(`practice/clients/${id}/`)).data });
  const timeline = useQuery({ queryKey: ["timeline", id], queryFn: async () => (await api.get<Timeline>(`practice/clients/${id}/timeline/`)).data, enabled: client.data?.relationship?.status === "active" });
  const resend = useMutation({ mutationFn: () => api.post(`practice/clients/${id}/resend-invite/`) });
  const newNote = useMutation({
    mutationFn: async () =>
      (await api.post<ClinicalDocument>(`practice/clients/${id}/documents/`, {
        doc_type: "progress_note", title: `Progress note ${new Date().toLocaleDateString()}`,
        text: NOTE_TEMPLATES[profile.data?.note_format ?? "soap"],
        session: timeline.data ? latestPastSession(timeline.data.sessions)?.id ?? null : null,
      })).data,
    onSuccess: (doc) => {
      queryClient.invalidateQueries({ queryKey: ["timeline", id] });
      navigate({ to: "/practice/clients/$clientId/documents/$docId", params: { clientId, docId: String(doc.id) } });
    },
  });

  if (client.isLoading) return <Box sx={{ display: "grid", placeItems: "center", py: 10 }}><CircularProgress /></Box>;
  if (!client.data) return <Container sx={{ py: 6 }}><Alert severity="warning">{getErrorMessage(client.error, "Client not found.")}</Alert></Container>;
  const c = client.data;
  const invited = c.relationship?.status === "invited";
  const openDoc = (docId: number) => navigate({ to: "/practice/clients/$clientId/documents/$docId", params: { clientId, docId: String(docId) } });

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <LinkButton to="/practice/clients" size="small" sx={{ ml: -1, mb: 1 }}>← All clients</LinkButton>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} spacing={1} mb={3}>
        <Box>
          <Typography variant="h4" component="h1">{c.display_name}</Typography>
          <Typography color="text.secondary">{c.email}</Typography>
        </Box>
        {invited && (
          <Stack direction="row" spacing={1} alignItems="center">
            <Chip label="Invite pending" />
            <Button size="small" onClick={() => resend.mutate()} disabled={resend.isPending || resend.isSuccess}>
              {resend.isSuccess ? "Sent" : "Resend invite"}
            </Button>
          </Stack>
        )}
      </Stack>
      <Stack spacing={3}>
        <SyntheticDataBanner />
        {invited ? (
          <Alert severity="info">{c.display_name} hasn't accepted your invitation yet. Their record opens once they connect.</Alert>
        ) : (
          <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "3fr 2fr" }, alignItems: "start" }}>
            <Stack spacing={3}>
              <PrepPanel clientId={id} />
              <BetweenSessionsPanel clientId={id} hasAccount={c.has_account} />
              <AskPanel clientId={id} />
              <Panel
                title="Sessions & notes"
                action={
                  <Stack direction="row" spacing={1}>
                    <Button size="small" onClick={() => setAddingSession(true)}>Add session</Button>
                    <Button size="small" startIcon={<UploadFileOutlined />} onClick={() => setImporting(true)}>Import</Button>
                    <Button size="small" startIcon={<EditNoteOutlined />} onClick={() => newNote.mutate()} disabled={newNote.isPending}>New note</Button>
                    <Button size="small" variant="contained" startIcon={<AutoAwesomeOutlined />} onClick={() => setDrafting(true)}>From transcript</Button>
                  </Stack>
                }
              >
                {timeline.data?.sessions.length === 0 && timeline.data.other_documents.length === 0 && (
                  <Typography color="text.secondary">No sessions or notes yet.</Typography>
                )}
                <List disablePadding>
                  {timeline.data?.sessions.map((s) => (
                    <Box key={s.id} sx={{ mb: 1.5 }}>
                      <Typography variant="subtitle2">
                        {formatDate(s.date)}{s.start_time && `, ${formatTime(s.start_time)}`} · {MODALITIES.find((m) => m.value === s.modality)?.label}
                        {s.status !== "completed" && <Chip size="small" label={s.status} sx={{ ml: 1, height: 20 }} />}
                      </Typography>
                      {s.documents.map((d) => (
                        <ListItemButton key={d.id} dense onClick={() => openDoc(d.id)} sx={{ borderRadius: 2, pl: 1.5 }}>
                          <ListItemText primary={d.title} secondary={`${DOC_LABELS[d.doc_type]}${d.imported_from ? " · imported" : ""}`} />
                          {d.status === "draft" && <Chip size="small" color="warning" label="Draft" />}
                        </ListItemButton>
                      ))}
                    </Box>
                  ))}
                  {!!timeline.data?.other_documents.length && (
                    <Box>
                      <Typography variant="subtitle2">Other documents</Typography>
                      {timeline.data.other_documents.map((d) => (
                        <ListItemButton key={d.id} dense onClick={() => openDoc(d.id)} sx={{ borderRadius: 2, pl: 1.5 }}>
                          <ListItemText primary={d.title} secondary={`${DOC_LABELS[d.doc_type]} · ${formatDate(d.created_at)}`} />
                        </ListItemButton>
                      ))}
                    </Box>
                  )}
                </List>
              </Panel>
            </Stack>
            <Stack spacing={3}>
              <ScreeningsPanel clientId={id} />
              <TreatmentPlanPanel clientId={id} />
              <HomeworkPanel clientId={id} hasAccount={c.has_account} />
            </Stack>
          </Box>
        )}
      </Stack>
      {timeline.data && (
        <DraftFromTranscriptDialog key={latestPastSession(timeline.data.sessions)?.id ?? 0} clientId={id} sessions={timeline.data.sessions}
                                   open={drafting} onClose={() => setDrafting(false)} />
      )}
      <ImportRecordsDialog clientId={id} open={importing} onClose={() => setImporting(false)} />
      {addingSession && <ScheduleSessionDialog clientId={id} open onClose={() => setAddingSession(false)} />}
    </Container>
  );
};
