import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import api, { getErrorMessage } from "../../api/client";
import type { ClinicalDocument } from "../../api/types";
import { formatDate } from "../../components/practice/format";
import { LinkButton } from "../../components/RouterLink";

/** Read, edit (while draft), sign, or amend one document in a client's record. */
export const DocumentPage = () => {
  const { clientId, docId } = useParams({ from: "/practice/clients/$clientId/documents/$docId" });
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const url = `practice/clients/${clientId}/documents/${docId}/`;
  const doc = useQuery({ queryKey: ["document", Number(clientId), Number(docId)], queryFn: async () => (await api.get<ClinicalDocument>(url)).data });
  const [text, setText] = useState("");
  const [addendum, setAddendum] = useState("");
  useEffect(() => { if (doc.data) setText(doc.data.text); }, [doc.data]);

  const refresh = (updated: ClinicalDocument) => {
    queryClient.setQueryData(["document", Number(clientId), Number(docId)], updated);
    queryClient.invalidateQueries({ queryKey: ["timeline", Number(clientId)] });
  };
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const discard = useMutation({
    mutationFn: () => api.delete(url),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ["document", Number(clientId), Number(docId)] });
      queryClient.invalidateQueries({ queryKey: ["timeline", Number(clientId)] });
      queryClient.invalidateQueries({ queryKey: ["practice-overview"] });
      navigate({ to: "/practice/clients/$clientId", params: { clientId } });
    },
  });
  const save = useMutation({ mutationFn: async () => (await api.patch<ClinicalDocument>(url, { text })).data, onSuccess: refresh });
  const sign = useMutation({
    mutationFn: async () => {
      if (text !== doc.data?.text) await api.patch(url, { text });
      return (await api.post<ClinicalDocument>(`${url}sign/`)).data;
    },
    onSuccess: refresh,
  });
  const amend = useMutation({
    mutationFn: async () => (await api.post<ClinicalDocument>(`${url}addendum/`, { text: addendum })).data,
    onSuccess: (created) => {
      setAddendum("");
      navigate({ to: "/practice/clients/$clientId/documents/$docId", params: { clientId, docId: String(created.id) } });
    },
  });

  if (doc.isLoading) return <Box sx={{ display: "grid", placeItems: "center", py: 10 }}><CircularProgress /></Box>;
  if (!doc.data) return <Container sx={{ py: 6 }}><Alert severity="warning">{getErrorMessage(doc.error, "Document not found.")}</Alert></Container>;
  const d = doc.data;

  return (
    <Container maxWidth="md" sx={{ py: { xs: 3, md: 5 } }}>
      <LinkButton to="/practice/clients/$clientId" params={{ clientId }} size="small" sx={{ ml: -1, mb: 1 }}>
        ← Back to client
      </LinkButton>
      <Typography variant="h4" component="h1">{d.title}</Typography>
      <Stack direction="row" spacing={1} my={1.5} flexWrap="wrap" useFlexGap>
        <Chip
          size="small"
          color={d.status === "draft" ? "warning" : "primary"}
          label={
            d.status === "draft"
              ? "Draft: not signed"
              : d.imported_from
                ? `Imported from ${d.imported_from}`
                : `Signed ${formatDate(d.signed_at)} by ${d.signed_by_name}`
          }
        />
        <Chip size="small" variant="outlined" label={formatDate(d.session_date)} />
        {d.amends && <Chip size="small" variant="outlined" label="Addendum" />}
        {d.title.includes("AI draft") && <Chip size="small" variant="outlined" label="AI draft: review every section" />}
      </Stack>

      {d.editable ? (
        <Stack spacing={2}>
          <TextField multiline minRows={14} value={text} onChange={(e) => setText(e.target.value)}
                     inputProps={{ style: { fontFamily: "inherit", lineHeight: 1.7 } }} />
          {(save.isError || sign.isError || discard.isError) && (
            <Alert severity="error">{getErrorMessage(save.error ?? sign.error ?? discard.error)}</Alert>
          )}
          <Stack direction="row" spacing={1.5} justifyContent="flex-end">
            <Button color="error" onClick={() => setConfirmingDelete(true)} sx={{ mr: "auto" }}>Delete draft</Button>
            <Button onClick={() => save.mutate()} disabled={save.isPending || text === d.text}>Save draft</Button>
            <Button variant="contained" onClick={() => sign.mutate()} disabled={sign.isPending || !text.trim()}>
              Sign note
            </Button>
          </Stack>
          <Typography variant="caption" color="text.secondary">
            Signing locks the note. Later corrections are added as addenda; the original is never changed.
          </Typography>
        </Stack>
      ) : (
        <Stack spacing={3}>
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 3, whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{d.text}</Paper>
          {d.status === "final" && d.doc_type === "progress_note" && (
            <Box>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>Add an addendum</Typography>
              <TextField multiline minRows={3} value={addendum} onChange={(e) => setAddendum(e.target.value)}
                         placeholder="Correction or later information, e.g. 'Client called on 10/12 to report…'" />
              <Button sx={{ mt: 1.5 }} variant="outlined" onClick={() => amend.mutate()} disabled={!addendum.trim() || amend.isPending}>
                Create addendum draft
              </Button>
            </Box>
          )}
        </Stack>
      )}
      <Dialog open={confirmingDelete} onClose={() => setConfirmingDelete(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete this draft?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            “{d.title}” will be deleted for good. It was never signed, so nothing in the client's signed record
            changes.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmingDelete(false)}>Keep it</Button>
          <Button color="error" variant="contained" disabled={discard.isPending} onClick={() => discard.mutate()}>
            Delete draft
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};
