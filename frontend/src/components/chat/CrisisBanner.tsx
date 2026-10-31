import { Alert, AlertTitle, Button, Stack } from "@mui/material";
import { ChatOutlined, Phone, Sms } from "@mui/icons-material";

/** Persistent, low-friction ways to reach a person right now. Shown while a conversation signals risk. */
export const CrisisBanner = ({ onDismiss }: { onDismiss: () => void }) => (
  <Alert
    severity="warning"
    onClose={onDismiss}
    sx={{ maxWidth: 820, mx: "auto", borderRadius: 3, "& .MuiAlert-message": { width: "100%" } }}
  >
    <AlertTitle>You don't have to go through this alone</AlertTitle>
    The 988 Suicide & Crisis Lifeline is free, confidential, and available 24/7. If you're in immediate danger, call 911.
    <Stack direction="row" spacing={1} mt={1.5} flexWrap="wrap" useFlexGap>
      <Button size="small" variant="contained" color="warning" startIcon={<Phone />} href="tel:988">
        Call 988
      </Button>
      <Button size="small" variant="outlined" color="warning" startIcon={<Sms />} href="sms:988">
        Text 988
      </Button>
      <Button
        size="small"
        variant="outlined"
        color="warning"
        startIcon={<ChatOutlined />}
        href="https://988lifeline.org/chat/"
        target="_blank"
        rel="noopener noreferrer"
      >
        Chat online
      </Button>
    </Stack>
  </Alert>
);
