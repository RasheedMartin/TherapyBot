import { useState } from "react";
import { Box, Button, Collapse, Paper, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";
import type { SharedSummary } from "../../api/types";

const day = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString([], { month: "long", day: "numeric" });

/** The latest session summary the client's therapist shared, with earlier ones on request. */
export const SessionSummaryCard = () => {
  const [showEarlier, setShowEarlier] = useState(false);
  const summaries = useQuery({
    queryKey: ["my-summaries"],
    queryFn: async () => (await api.get<SharedSummary[]>("care-team/summaries/")).data,
  });
  const [latest, ...earlier] = summaries.data ?? [];
  if (!latest) return null;

  const when = (s: SharedSummary) => (s.session_date ? `Session on ${day(s.session_date)}` : `Shared ${day(s.shared_at)}`);
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4 }}>
      <Typography variant="h6" component="h2">From your last session</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
        {latest.therapist_name}, {when(latest).charAt(0).toLowerCase() + when(latest).slice(1)}
      </Typography>
      <Typography sx={{ mt: 1.5, whiteSpace: "pre-wrap", maxWidth: 720 }}>{latest.text}</Typography>
      {earlier.length > 0 && (
        <Box mt={2}>
          <Button size="small" sx={{ ml: -1 }} onClick={() => setShowEarlier((v) => !v)}>
            {showEarlier ? "Hide earlier summaries" : `Show earlier summaries (${earlier.length})`}
          </Button>
          <Collapse in={showEarlier} unmountOnExit>
            <Stack spacing={2} mt={1.5}>
              {earlier.map((s) => (
                <Box key={s.id} sx={{ pt: 1.5, borderTop: 1, borderColor: "divider" }}>
                  <Typography variant="body2" color="text.secondary">{when(s)}</Typography>
                  <Typography sx={{ mt: 0.5, whiteSpace: "pre-wrap", maxWidth: 720 }}>{s.text}</Typography>
                </Box>
              ))}
            </Stack>
          </Collapse>
        </Box>
      )}
    </Paper>
  );
};
