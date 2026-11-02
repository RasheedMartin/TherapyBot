import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { UploadFileOutlined } from "@mui/icons-material";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import type { ImportedDocument, ImportPreview } from "../../api/types";

const TYPES: { value: ImportedDocument["doc_type"]; label: string }[] = [
  { value: "progress_note", label: "Progress note" },
  { value: "intake", label: "Intake" },
  { value: "transcript", label: "Transcript" },
  { value: "other", label: "Other" },
];

type Row = ImportedDocument & { key: string; filename: string; include: boolean; open: boolean };

/**
 * Bring existing records into a client's record: upload exports from another system (PDF, Word, text), review
 * how they were split, then import. Nothing is saved until the therapist confirms.
 */
export const ImportRecordsDialog = ({ clientId, open, onClose }: { clientId: number; open: boolean; onClose: () => void }) => {
  const queryClient = useQueryClient();
  const [files, setFiles] = useState<File[]>([]);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [fileErrors, setFileErrors] = useState<{ filename: string; error: string }[]>([]);

  const reset = () => {
    setFiles([]);
    setRows(null);
    setFileErrors([]);
  };
  const close = () => {
    reset();
    onClose();
  };

  const preview = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      return (
        await api.post<ImportPreview>(`practice/clients/${clientId}/import/preview/`, form, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data;
    },
    onSuccess: (data) => {
      setFileErrors(data.files.filter((f) => f.error).map((f) => ({ filename: f.filename, error: f.error! })));
      setRows(
        data.files.flatMap((f) =>
          f.documents.map((d, i) => ({ ...d, key: `${f.filename}-${i}`, filename: f.filename, include: true, open: false })),
        ),
      );
    },
  });

  const save = useMutation({
    mutationFn: async () =>
      (
        await api.post<{ created: number; sessions_created: number }>(`practice/clients/${clientId}/import/`, {
          documents: rows!
            .filter((r) => r.include)
            .map(({ title, doc_type, session_date, text, filename }) => ({ title, doc_type, session_date, text, filename })),
        })
      ).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["timeline", clientId] });
      close();
    },
  });

  const update = (key: string, patch: Partial<Row>) =>
    setRows((current) => current?.map((r) => (r.key === key ? { ...r, ...patch } : r)) ?? null);
  const selected = rows?.filter((r) => r.include).length ?? 0;
  const missingTitle = rows?.some((r) => r.include && !r.title.trim());

  return (
    <Dialog open={open} onClose={close} maxWidth="md" fullWidth>
      <DialogTitle>Import existing records</DialogTitle>
      <DialogContent dividers>
        {!rows ? (
          <Stack spacing={2}>
            <Typography color="text.secondary">
              Upload notes exported from your current system (PDF, Word or text). Exports with many notes are split
              into one document per note, each with a suggested date and type you can check before importing.
            </Typography>
            <Button component="label" variant="outlined" startIcon={<UploadFileOutlined />} sx={{ alignSelf: "flex-start" }}>
              Choose files
              <input
                hidden
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.md"
                onChange={(e) => setFiles(Array.from(e.target.files ?? []).slice(0, 10))}
              />
            </Button>
            {files.length > 0 && (
              <Typography variant="body2">{files.map((f) => f.name).join(", ")}</Typography>
            )}
            <Typography variant="caption" color="text.secondary">
              Up to 10 files, 10 MB each. Scanned PDFs (images of pages) can't be read; export as text-based PDF or Word.
            </Typography>
            {preview.isError && <Alert severity="error">{getErrorMessage(preview.error)}</Alert>}
          </Stack>
        ) : (
          <Stack spacing={2}>
            {fileErrors.map((e) => (
              <Alert key={e.filename} severity="warning">
                <strong>{e.filename}</strong>: {e.error}
              </Alert>
            ))}
            {rows.length === 0 && <Typography color="text.secondary">No readable notes were found.</Typography>}
            {rows.map((r) => (
              <Box key={r.key} sx={{ p: 1.5, borderRadius: 2, border: 1, borderColor: "divider", opacity: r.include ? 1 : 0.55 }}>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
                  <Checkbox checked={r.include} onChange={(e) => update(r.key, { include: e.target.checked })} sx={{ alignSelf: "flex-start" }} />
                  <TextField size="small" label="Title" value={r.title} onChange={(e) => update(r.key, { title: e.target.value })}
                             sx={{ flex: 1, minWidth: { sm: 220 } }} error={r.include && !r.title.trim()} />
                  <TextField size="small" select label="Type" value={r.doc_type} sx={{ width: { sm: 170 }, flexShrink: 0 }}
                             onChange={(e) => update(r.key, { doc_type: e.target.value as Row["doc_type"] })}>
                    {TYPES.map((t) => <MenuItem key={t.value} value={t.value}>{t.label}</MenuItem>)}
                  </TextField>
                  <TextField size="small" type="date" label="Date" value={r.session_date ?? ""} sx={{ width: { sm: 170 }, flexShrink: 0 }}
                             onChange={(e) => update(r.key, { session_date: e.target.value || null })}
                             slotProps={{ inputLabel: { shrink: true } }} />
                </Stack>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ pl: { sm: 6 }, mt: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    {r.filename}, {r.text.length.toLocaleString()} characters
                    {!r.session_date && ", no date found"}
                  </Typography>
                  <Button size="small" onClick={() => update(r.key, { open: !r.open })}>{r.open ? "Hide text" : "Show text"}</Button>
                </Stack>
                <Collapse in={r.open} unmountOnExit>
                  <Typography component="pre" variant="body2"
                              sx={{ whiteSpace: "pre-wrap", fontFamily: "inherit", m: 0, mt: 1, p: 1.5, bgcolor: "action.hover",
                                    borderRadius: 1, maxHeight: 240, overflowY: "auto" }}>
                    {r.text}
                  </Typography>
                </Collapse>
              </Box>
            ))}
            <Typography variant="caption" color="text.secondary">
              Dated notes, transcripts and intakes are added to the session on that date (a completed session is created
              if there isn't one). Imported documents are saved as final, since they were signed in the original system.
            </Typography>
            {save.isError && <Alert severity="error">{getErrorMessage(save.error)}</Alert>}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {rows && <Button onClick={reset} sx={{ mr: "auto" }}>Start over</Button>}
        <Button onClick={close}>Cancel</Button>
        {!rows ? (
          <Button variant="contained" disabled={!files.length || preview.isPending} onClick={() => preview.mutate()}>
            {preview.isPending ? "Reading…" : "Read files"}
          </Button>
        ) : (
          <Button variant="contained" disabled={!selected || !!missingTitle || save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "Importing…" : `Import ${selected} document${selected === 1 ? "" : "s"}`}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};
