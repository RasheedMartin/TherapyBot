import { Alert, Box, Button, Container, List, ListItemButton, ListItemText, Paper, Skeleton, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import api, { getErrorMessage } from "../../api/client";
import type { DraftSummary, PracticeOverview } from "../../api/types";
import { formatDate } from "../../components/practice/format";
import { SyntheticDataBanner } from "../../components/practice/SyntheticDataBanner";

const Section = ({ title, empty, children }: { title: string; empty: string | false; children: React.ReactNode }) => (
  <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 }, borderRadius: 4 }}>
    <Typography variant="h6" component="h2" mb={1}>{title}</Typography>
    {empty ? <Typography color="text.secondary">{empty}</Typography> : children}
  </Paper>
);

/** Documentation across clients: notes still to write, drafts to sign, and what was signed recently. */
export const NotesQueue = () => {
  const navigate = useNavigate();
  const overview = useQuery({
    queryKey: ["practice-overview"],
    queryFn: async () => (await api.get<PracticeOverview>("practice/overview/")).data,
  });
  const o = overview.data;
  const openDoc = (d: DraftSummary) =>
    navigate({ to: "/practice/clients/$clientId/documents/$docId", params: { clientId: String(d.client_id), docId: String(d.id) } });
  const docList = (docs: DraftSummary[], when: (d: DraftSummary) => string) => (
    <List disablePadding>
      {docs.map((d) => (
        <ListItemButton key={d.id} onClick={() => openDoc(d)} sx={{ borderRadius: 2, px: 1.5 }}>
          <ListItemText primary={`${d.client_name}: ${d.title}`} secondary={when(d)} />
        </ListItemButton>
      ))}
    </List>
  );

  return (
    <Container maxWidth="md" sx={{ py: { xs: 3, md: 5 } }}>
      <Typography variant="h4" component="h1">Notes</Typography>
      <Typography color="text.secondary" mb={3}>
        Sessions from the last two weeks that still need a note, drafts waiting for your signature, and your recent notes.
      </Typography>
      <Stack spacing={3}>
        <SyntheticDataBanner />
        {overview.isError && <Alert severity="error">{getErrorMessage(overview.error)}</Alert>}
        {overview.isLoading && <Skeleton variant="rounded" height={200} />}
        {o && (
          <>
            <Section title="To write" empty={!o.needs_note.length && "Every completed session has a note."}>
              <Stack divider={<Box sx={{ borderTop: 1, borderColor: "divider" }} />}>
                {o.needs_note.map((s) => (
                  <Stack key={s.id} direction="row" justifyContent="space-between" alignItems="center" spacing={2} sx={{ py: 1.25 }}>
                    <Box>
                      <Typography fontWeight={600}>{s.client_name}</Typography>
                      <Typography variant="body2" color="text.secondary">Session on {formatDate(s.date)}</Typography>
                    </Box>
                    <Button size="small" variant="outlined"
                            onClick={() => navigate({ to: "/practice/clients/$clientId", params: { clientId: String(s.client_id) } })}>
                      Write note
                    </Button>
                  </Stack>
                ))}
              </Stack>
            </Section>
            <Section title="To sign" empty={!o.drafts.length && "No drafts waiting."}>
              {docList(o.drafts, (d) => `Draft, last edited ${formatDate(d.updated_at)}`)}
            </Section>
            <Section title="Recently signed" empty={!o.recently_signed.length && "Notes you sign appear here."}>
              {docList(o.recently_signed, (d) => (d.session_date ? `Session on ${formatDate(d.session_date)}` : "Undated"))}
            </Section>
          </>
        )}
      </Stack>
    </Container>
  );
};
