import { useState } from "react";
import {
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { ContentCopy, Phone } from "@mui/icons-material";
import type { Profile, Provider } from "../../api/types";

interface CallScriptDialogProps {
  provider: Pick<Provider, "name" | "credential" | "phone" | "is_organization"> | null;
  profile: Profile | undefined;
  onClose: () => void;
  onLogCall: () => void;
}

const QUESTIONS = [
  "Are you accepting new clients?",
  "Do you take my insurance, or what is your self-pay rate? Do you offer a sliding scale?",
  "Do you offer telehealth, in-person sessions, or both?",
  "What approaches do you use (for example CBT or DBT)?",
  "What does the first appointment look like, and when is the next opening?",
];

const buildCallScript = (provider: CallScriptDialogProps["provider"], profile?: Profile) => {
  if (!provider) return "";
  const name = profile?.display_name || "[your name]";
  // Goals are free text, so quote them after a colon rather than splicing them into a sentence
  const reason = profile?.goals?.trim().replace(/[.\s]+$/, "") || "stress and anxiety";
  const who = provider.is_organization ? "your practice" : provider.name;
  const insurance = profile?.insurance?.trim();
  const format =
    profile?.session_format === "telehealth"
      ? " I'd prefer telehealth sessions."
      : profile?.session_format === "in_person"
        ? " I'd prefer to meet in person."
        : "";
  return (
    `Hi, my name is ${name}. I found ${who} in a provider directory and I'm looking to start therapy. ` +
    `The main thing I'd like help with is: ${reason}. Are you currently accepting new clients?` +
    (insurance ? ` I have ${insurance}. Do you accept it?` : " Could you tell me about your fees?") +
    format
  );
};

export const CallScriptDialog = ({ provider, profile, onClose, onLogCall }: CallScriptDialogProps) => {
  const [copied, setCopied] = useState(false);
  const [asked, setAsked] = useState<Set<number>>(new Set());
  const script = buildCallScript(provider, profile);

  const toggle = (i: number) =>
    setAsked((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  return (
    <Dialog open={!!provider} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>What to say when you call</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" mb={2}>
          Calling can feel daunting. It's okay to read this word for word, or to leave it as a voicemail.
        </Typography>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 3, bgcolor: "action.hover" }}>
          <Typography>{script}</Typography>
          <Button
            size="small"
            startIcon={<ContentCopy fontSize="small" />}
            sx={{ mt: 1 }}
            onClick={() => {
              navigator.clipboard?.writeText(script);
              setCopied(true);
            }}
          >
            {copied ? "Copied" : "Copy"}
          </Button>
        </Paper>
        <Typography variant="subtitle2" mt={3} mb={1}>
          Questions to ask
        </Typography>
        <Stack>
          {QUESTIONS.map((q, i) => (
            <FormControlLabel
              key={q}
              control={<Checkbox size="small" checked={asked.has(i)} onChange={() => toggle(i)} />}
              label={<Typography variant="body2">{q}</Typography>}
            />
          ))}
        </Stack>
        {!profile?.goals && (
          <Box mt={2}>
            <Typography variant="caption" color="text.secondary">
              Tip: add your goals and insurance in your profile to personalize this script.
            </Typography>
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ flexWrap: "wrap", gap: 1 }}>
        <Button onClick={onClose}>Close</Button>
        <Button
          variant="outlined"
          onClick={() => {
            onLogCall();
            onClose();
          }}
        >
          Mark as contacted
        </Button>
        {provider?.phone && (
          <Button variant="contained" startIcon={<Phone />} href={`tel:${provider.phone}`}>
            Call {provider.phone}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};
