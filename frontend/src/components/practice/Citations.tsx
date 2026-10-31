import { useState } from "react";
import {
  Box,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { Close } from "@mui/icons-material";
import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import type { Citation, CitedItem, ClinicalDocument } from "../../api/types";
import { formatDate } from "./format";

const DOC_LABELS: Record<string, string> = {
  progress_note: "Progress note",
  transcript: "Transcript",
  intake: "Intake",
  client_upload: "Client upload",
  chat_summary: "Companion chat summary, shared by the client",
  other: "Document",
};

/** The source document behind a citation, with the cited passage highlighted. */
const SourceDialog = ({ clientId, citation, onClose }: { clientId: number; citation: Citation | null; onClose: () => void }) => {
  const doc = useQuery({
    queryKey: ["document", clientId, citation?.document_id],
    queryFn: async () => (await api.get<ClinicalDocument>(`practice/clients/${clientId}/documents/${citation!.document_id}/`)).data,
    enabled: !!citation?.document_id,
  });
  const text = doc.data?.text ?? "";
  // The snippet has collapsed whitespace; match it against the original text with any whitespace in between
  const words = (citation?.snippet.replace(/…$/, "") ?? "").trim().split(/\s+/).slice(0, 20);
  const pattern = words.length ? new RegExp(words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+")) : null;
  const match = pattern ? pattern.exec(text) : null;

  return (
    <Dialog open={!!citation} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ pr: 6 }}>
        {doc.data?.title ?? "Source"}
        <Typography variant="body2" color="text.secondary">
          [{citation?.label}] {DOC_LABELS[citation?.doc_type ?? "other"]} · {formatDate(citation?.session_date ?? null)}
        </Typography>
        <IconButton onClick={onClose} aria-label="Close" sx={{ position: "absolute", right: 12, top: 12 }}>
          <Close />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {doc.isLoading && <CircularProgress />}
        {citation && !citation.document_id && (
          <>
            <Typography sx={{ lineHeight: 1.7 }}>{citation.snippet}</Typography>
            <Typography variant="caption" color="text.secondary" display="block" mt={2}>
              AI summary of what the client said to the companion between sessions. Not a clinical observation.
            </Typography>
          </>
        )}
        {doc.data && (
          <Typography component="div" sx={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
            {match ? (
              <>
                {text.slice(0, match.index)}
                <Box component="mark" sx={{ bgcolor: "warning.light", color: "inherit", px: 0.25, borderRadius: 0.5 }}>
                  {match[0]}
                </Box>
                {text.slice(match.index + match[0].length)}
              </>
            ) : (
              text
            )}
          </Typography>
        )}
      </DialogContent>
    </Dialog>
  );
};

/** Clickable [S#] chips for a list of labels. Each opens the source document. */
export const CitationChips = ({
  labels,
  sources,
  clientId,
}: {
  labels: string[];
  sources: Citation[];
  clientId: number;
}) => {
  const [open, setOpen] = useState<Citation | null>(null);
  const byLabel = new Map(sources.map((s) => [s.label, s]));
  return (
    <>
      <Box component="span" sx={{ display: "inline-flex", gap: 0.5, flexWrap: "wrap", verticalAlign: "middle", ml: 0.5 }}>
        {labels.map((label) => {
          const source = byLabel.get(label);
          if (!source) return null;
          return (
            <Tooltip key={label} title={source.snippet}>
              <Chip
                size="small"
                variant="outlined"
                color="primary"
                label={`${DOC_LABELS[source.doc_type] ?? "Doc"} · ${formatDate(source.session_date)}`}
                onClick={() => setOpen(source)}
                sx={{ height: 22, fontSize: 12 }}
              />
            </Tooltip>
          );
        })}
      </Box>
      <SourceDialog clientId={clientId} citation={open} onClose={() => setOpen(null)} />
    </>
  );
};

/** Prose containing [S#] markers, rendered with the markers replaced by clickable chips. */
export const CitedText = ({ text, sources, clientId }: { text: string; sources: Citation[]; clientId: number }) => {
  const parts = text.split(/((?:\[S\d+\])+)/g);
  return (
    <Typography component="div" sx={{ lineHeight: 1.8 }}>
      {parts.map((part, i) =>
        /^\[S\d+\]/.test(part) ? (
          <CitationChips key={i} labels={part.match(/S\d+/g) ?? []} sources={sources} clientId={clientId} />
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </Typography>
  );
};

export const CitedList = ({
  title,
  items,
  sources,
  clientId,
}: {
  title: string;
  items: CitedItem[];
  sources: Citation[];
  clientId: number;
}) =>
  items.length ? (
    <Box>
      <Typography variant="overline" color="text.secondary">
        {title}
      </Typography>
      <Stack spacing={1} component="ul" sx={{ pl: 2.5, m: 0 }}>
        {items.map((item) => (
          <Typography component="li" key={item.text} sx={{ lineHeight: 1.8 }}>
            {item.text}
            <CitationChips labels={item.sources} sources={sources} clientId={clientId} />
          </Typography>
        ))}
      </Stack>
    </Box>
  ) : null;
