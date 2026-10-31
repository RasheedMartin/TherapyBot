import { useState } from "react";
import { Alert, Box, Button, Chip, Collapse, Divider, Skeleton, Stack, Typography } from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import type { BetweenSessions, SharedConversation } from "../../api/types";
import { formatDate } from "./format";
import { Panel } from "./AssistantPanels";

const Transcript = ({ messages }: { messages: NonNullable<SharedConversation["messages"]> }) => (
  <Stack spacing={1} sx={{ mt: 1, p: 1.5, borderRadius: 2, bgcolor: "action.hover", maxHeight: 320, overflowY: "auto" }}>
    {messages.map((m, i) => (
      <Typography key={i} variant="body2">
        <strong>{m.role === "user" ? "Client" : "Companion"}:</strong> {m.content}
      </Typography>
    ))}
  </Stack>
);

const ConversationItem = ({ item }: { item: SharedConversation }) => {
  const [showChat, setShowChat] = useState(false);
  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="baseline" justifyContent="space-between">
        <Typography fontWeight={600} noWrap>{item.title || "Conversation"}</Typography>
        <Typography variant="caption" color="text.secondary" flexShrink={0}>
          {formatDate(item.updated_at)} · {item.message_count} messages
        </Typography>
      </Stack>
      {item.flagged && (
        <Chip size="small" color="warning" label="Safety check flagged risk here" sx={{ mt: 0.75 }} />
      )}
      {item.summary && <Typography variant="body2" sx={{ mt: 0.5, lineHeight: 1.6 }}>{item.summary}</Typography>}
      {item.messages && (
        <>
          <Button size="small" sx={{ ml: -1 }} onClick={() => setShowChat((v) => !v)}>
            {showChat ? "Hide conversation" : "Read conversation"}
          </Button>
          <Collapse in={showChat} unmountOnExit><Transcript messages={item.messages} /></Collapse>
        </>
      )}
    </Box>
  );
};

/** What the client did in the companion since the last session, limited to what they chose to share. */
export const BetweenSessionsPanel = ({ clientId, hasAccount }: { clientId: number; hasAccount: boolean }) => {
  const data = useQuery({
    queryKey: ["between-sessions", clientId],
    queryFn: async () => (await api.get<BetweenSessions>(`practice/clients/${clientId}/between-sessions/`)).data,
    enabled: hasAccount,
    staleTime: 5 * 60 * 1000, // summaries take a model call; don't regenerate on every visit
  });
  const d = data.data;
  const sharesChat = d && (d.sharing.share_chat_summaries || d.sharing.share_raw_chat);

  return (
    <Panel title="Between sessions">
      {!hasAccount && <Typography color="text.secondary">Available once the client accepts your invitation.</Typography>}
      {data.isLoading && <><Skeleton height={24} /><Skeleton height={64} /></>}
      {data.isError && <Alert severity="error">{getErrorMessage(data.error)}</Alert>}
      {d && (
        <Stack spacing={2}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip size="small" variant="outlined" label={`Since ${formatDate(d.since)}`} />
            {d.chat_flags > 0 && <Chip size="small" color="warning" label={`${d.chat_flags} safety flag${d.chat_flags > 1 ? "s" : ""} from chat`} />}
            {!d.sharing.share_checkins && <Chip size="small" variant="outlined" label="Check-ins not shared" />}
          </Stack>
          {!sharesChat && (
            <Typography color="text.secondary">
              This client hasn't chosen to share companion conversations. Safety flags still reach you.
            </Typography>
          )}
          {sharesChat && d.conversations.length === 0 && (
            <Typography color="text.secondary">No shared companion conversations since then.</Typography>
          )}
          {d.conversations.map((item, i) => (
            <Box key={item.id}>
              {i > 0 && <Divider sx={{ mb: 2 }} />}
              <ConversationItem item={item} />
            </Box>
          ))}
          {sharesChat && (
            <Typography variant="caption" color="text.secondary">
              Shared by the client, who can keep any conversation private. Summaries are AI-generated from what the
              client wrote, not clinical observations.
            </Typography>
          )}
        </Stack>
      )}
    </Panel>
  );
};
