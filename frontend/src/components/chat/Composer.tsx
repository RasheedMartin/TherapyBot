import { useEffect, useRef } from "react";
import { Box, IconButton, InputBase, Paper, Tooltip, Typography } from "@mui/material";
import { ArrowUpward } from "@mui/icons-material";

const MAX_LENGTH = 4000;

interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
  autoFocusKey?: unknown;
}

export const Composer = ({ value, onChange, onSend, disabled, autoFocusKey }: ComposerProps) => {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const canSend = !disabled && value.trim().length > 0 && value.length <= MAX_LENGTH;

  useEffect(() => {
    inputRef.current?.focus();
  }, [autoFocusKey]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Enter sends, Shift+Enter adds a newline; ignore while an IME is composing
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (canSend) onSend();
    }
  };

  return (
    <Box sx={{ px: { xs: 1.5, sm: 3 }, pb: { xs: 1.5, sm: 2 }, pt: 1 }}>
      <Paper
        variant="outlined"
        component="form"
        onSubmit={(e) => {
          e.preventDefault();
          if (canSend) onSend();
        }}
        sx={{
          display: "flex",
          alignItems: "flex-end",
          gap: 1,
          pl: 2,
          pr: 1,
          py: 1,
          borderRadius: 4,
          maxWidth: 820,
          mx: "auto",
          "&:focus-within": { borderColor: "primary.main" },
        }}
      >
        <InputBase
          inputRef={inputRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Share what's on your mind…"
          multiline
          maxRows={8}
          fullWidth
          inputProps={{ "aria-label": "Message", maxLength: MAX_LENGTH + 200 }}
          sx={{ py: 0.75 }}
        />
        <Tooltip title="Send (Enter)">
          <span>
            <IconButton
              type="submit"
              disabled={!canSend}
              aria-label="Send message"
              sx={{
                bgcolor: "primary.main",
                color: "primary.contrastText",
                "&:hover": { bgcolor: "primary.dark" },
                "&.Mui-disabled": { bgcolor: "action.disabledBackground" },
              }}
            >
              <ArrowUpward />
            </IconButton>
          </span>
        </Tooltip>
      </Paper>
      <Typography
        variant="caption"
        color={value.length > MAX_LENGTH ? "error" : "text.secondary"}
        display="block"
        textAlign="center"
        mt={1}
      >
        {value.length > MAX_LENGTH
          ? `Message is too long (${value.length}/${MAX_LENGTH} characters).`
          : "TherapyBot can make mistakes and isn't a substitute for professional care. In crisis, call or text 988."}
      </Typography>
    </Box>
  );
};
