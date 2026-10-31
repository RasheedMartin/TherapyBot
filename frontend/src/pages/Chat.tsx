import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Drawer,
  IconButton,
  Stack,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import { ChecklistRtl, Menu as MenuIcon, PersonSearchOutlined } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import api, { getErrorMessage } from "../api/client";
import { streamMessage } from "../api/stream";
import { THERAPY_TYPES, type Conversation, type ConversationDetail, type PlanDraft } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { ConversationList } from "../components/chat/ConversationList";
import { Composer } from "../components/chat/Composer";
import { CareTeamSharing } from "../components/chat/CareTeamSharing";
import { useActiveCareTeam } from "../components/chat/careTeam";
import { CrisisBanner } from "../components/chat/CrisisBanner";
import { MessageBubble, TypingIndicator } from "../components/chat/MessageBubble";
import { PlanEditor } from "../components/plans/PlanEditor";

const SIDEBAR_WIDTH = 300;

const SUGGESTIONS = [
  "I've been feeling overwhelmed at work lately.",
  "How can I calm down when I feel anxious?",
  "I keep arguing with my family and don't know how to stop.",
  "I can't stop overthinking at night.",
];

export const ChatPage = () => {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { c: activeId } = useSearch({ from: "/chat" });
  const careTeam = useActiveCareTeam();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [therapyType, setTherapyType] = useState<string>(THERAPY_TYPES[0]);
  const [pending, setPending] = useState<string | null>(null);
  const [streamed, setStreamed] = useState("");
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const conversationsQuery = useQuery({
    queryKey: ["conversations"],
    queryFn: async () => (await api.get<Conversation[]>("conversations/")).data,
  });

  const conversationQuery = useQuery({
    queryKey: ["conversation", activeId],
    queryFn: async () => (await api.get<ConversationDetail>(`conversations/${activeId}/`)).data,
    enabled: activeId != null,
  });

  const conversation = activeId != null ? conversationQuery.data : undefined;
  const messages = conversation?.messages ?? [];

  // Keep support options in view while the conversation signals risk; reappears if risk shows up again
  const lastRiskyId = [...messages].reverse().find((m) => m.role === "assistant" && (m.risk_level ?? "none") !== "none")?.id;
  const [dismissedRiskId, setDismissedRiskId] = useState<number | null>(null);
  const showCrisisBanner = lastRiskyId != null && lastRiskyId !== dismissedRiskId;

  const selectConversation = (id: number | undefined) => {
    navigate({ to: "/chat", search: id != null ? { c: id } : {} });
    setMobileOpen(false);
    setError(null);
    setPending(null);
  };

  const [planDraft, setPlanDraft] = useState<PlanDraft | null>(null);
  const draftPlan = useMutation({
    mutationFn: async (conversationId: number) =>
      (await api.post<PlanDraft>("plans/draft/", { conversation: conversationId })).data,
    onSuccess: setPlanDraft,
    onError: (err) => setError(getErrorMessage(err, "Couldn't draft a plan right now. Please try again.")),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`conversations/${id}/`),
    onSuccess: (_, id) => {
      queryClient.setQueryData<Conversation[]>(["conversations"], (old) => old?.filter((c) => c.id !== id));
      queryClient.removeQueries({ queryKey: ["conversation", id] });
      if (id === activeId) selectConversation(undefined);
    },
    onError: (err) => setError(getErrorMessage(err, "Couldn't delete that conversation.")),
  });

  const sendMutation = useMutation({
    mutationFn: async ({ text, conversationId }: { text: string; conversationId?: number }) => {
      let id = conversationId;
      if (id == null) {
        const created = await api.post<Conversation>("conversations/", { therapy_type: therapyType });
        id = created.data.id;
        queryClient.setQueryData<ConversationDetail>(["conversation", id], { ...created.data, messages: [], care_summary: "" });
        navigate({ to: "/chat", search: { c: id }, replace: true });
      }
      const data = await streamMessage(id, text, (delta) => setStreamed((prev) => prev + delta));
      return { id, data };
    },
    onMutate: ({ text }) => {
      setPending(text);
      setStreamed("");
      setError(null);
      setDraft("");
    },
    onSuccess: ({ id, data }) => {
      queryClient.setQueryData<ConversationDetail>(["conversation", id], (old) => ({
        care_summary: old?.care_summary ?? "",
        ...data.conversation,
        messages: [...(old?.messages ?? []), ...data.messages],
      }));
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (err, { text }) => {
      setError(getErrorMessage(err, "TherapyBot couldn't respond. Your message wasn't sent — please try again."));
      setDraft((current) => current || text);
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onSettled: () => {
      setPending(null);
      setStreamed("");
    },
  });

  const handleSend = (text = draft) => {
    const trimmed = text.trim();
    if (!trimmed || sendMutation.isPending) return;
    sendMutation.mutate({ text: trimmed, conversationId: activeId });
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: streamed ? "auto" : "smooth", block: "end" });
  }, [messages.length, pending, streamed]);

  const sidebar = (
    <ConversationList
      conversations={conversationsQuery.data}
      loading={conversationsQuery.isLoading}
      activeId={activeId ?? null}
      onSelect={selectConversation}
      onNew={() => selectConversation(undefined)}
      onDelete={(id) => deleteMutation.mutate(id)}
    />
  );

  const showEmptyState = activeId == null && !pending;
  const notFound = activeId != null && conversationQuery.isError;

  return (
    <Box sx={{ display: "flex", height: { xs: "calc(100dvh - 56px)", sm: "calc(100dvh - 64px)" }, minHeight: 0 }}>
      {isDesktop ? (
        <Box
          component="aside"
          sx={{ width: SIDEBAR_WIDTH, flexShrink: 0, borderRight: 1, borderColor: "divider", bgcolor: "background.paper" }}
        >
          {sidebar}
        </Box>
      ) : (
        <Drawer
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          slotProps={{ paper: { sx: { width: SIDEBAR_WIDTH } } }}
        >
          {sidebar}
        </Drawer>
      )}

      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Stack
          direction="row"
          alignItems="center"
          spacing={1}
          sx={{ px: { xs: 1, sm: 3 }, py: 1.25, borderBottom: 1, borderColor: "divider", minHeight: 56 }}
        >
          {!isDesktop && (
            <IconButton onClick={() => setMobileOpen(true)} aria-label="Open conversations">
              <MenuIcon />
            </IconButton>
          )}
          <Typography variant="subtitle1" fontWeight={600} noWrap sx={{ flex: 1 }}>
            {conversation?.title || "New conversation"}
          </Typography>
          <Chip
            size="small"
            label={conversation?.therapy_type ?? therapyType}
            color="primary"
            variant="outlined"
            sx={{ display: { xs: "none", sm: "inline-flex" } }}
          />
          {conversation && <CareTeamSharing conversation={conversation} />}
          {activeId != null && messages.length > 0 && (
            <Tooltip title="Turn this conversation into a plan or routine">
              <Button
                size="small"
                variant="outlined"
                startIcon={draftPlan.isPending ? <CircularProgress size={16} /> : <ChecklistRtl />}
                onClick={() => draftPlan.mutate(activeId)}
                disabled={draftPlan.isPending || sendMutation.isPending}
              >
                {draftPlan.isPending ? "Drafting…" : "Make a plan"}
              </Button>
            </Tooltip>
          )}
          <Tooltip title="Find a therapist near you">
            <IconButton component={Link} to="/find-care" aria-label="Find care" size="small">
              <PersonSearchOutlined />
            </IconButton>
          </Tooltip>
        </Stack>

        <Box sx={{ flex: 1, overflowY: "auto", px: { xs: 1.5, sm: 3 }, py: 3 }}>
          <Stack spacing={2.5} sx={{ maxWidth: 820, mx: "auto" }}>
            {showEmptyState && (
              <Box sx={{ textAlign: "center", py: { xs: 2, md: 6 } }}>
                <Typography variant="h4" component="h1" gutterBottom>
                  Hi{user ? `, ${user.display_name}` : ""}. How are you feeling today?
                </Typography>
                <Typography color="text.secondary" sx={{ maxWidth: 520, mx: "auto" }}>
                  This is a safe space. Choose a focus for this conversation, then share whatever is on your mind.
                </Typography>

                <Typography variant="overline" color="text.secondary" display="block" mt={4} mb={1}>
                  Focus
                </Typography>
                <Stack direction="row" flexWrap="wrap" justifyContent="center" gap={1}>
                  {THERAPY_TYPES.map((type) => (
                    <Chip
                      key={type}
                      label={type}
                      onClick={() => setTherapyType(type)}
                      color={type === therapyType ? "primary" : "default"}
                      variant={type === therapyType ? "filled" : "outlined"}
                    />
                  ))}
                </Stack>

                <Typography variant="overline" color="text.secondary" display="block" mt={4} mb={1}>
                  Not sure where to start?
                </Typography>
                <Box
                  sx={{
                    display: "grid",
                    gap: 1.5,
                    gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
                    maxWidth: 640,
                    mx: "auto",
                  }}
                >
                  {SUGGESTIONS.map((s) => (
                    <Box
                      key={s}
                      component="button"
                      type="button"
                      onClick={() => handleSend(s)}
                      sx={{
                        textAlign: "left",
                        p: 2,
                        borderRadius: 3,
                        border: 1,
                        borderColor: "divider",
                        bgcolor: "background.paper",
                        color: "text.primary",
                        font: "inherit",
                        cursor: "pointer",
                        transition: "border-color 0.2s",
                        "&:hover, &:focus-visible": { borderColor: "primary.main" },
                      }}
                    >
                      {s}
                    </Box>
                  ))}
                </Box>
              </Box>
            )}

            {activeId != null && conversationQuery.isLoading && (
              <Box sx={{ display: "grid", placeItems: "center", py: 8 }}>
                <CircularProgress />
              </Box>
            )}

            {notFound && (
              <Alert severity="warning">This conversation couldn't be found. It may have been deleted.</Alert>
            )}

            {messages.map((m) => (
              <MessageBubble
                key={m.id}
                role={m.role}
                content={m.content}
                isCrisis={m.is_crisis}
                sources={m.sources}
                // Only the latest reply offers a next step, so old suggestions don't pile up
                action={m.id === messages[messages.length - 1]?.id ? m.suggested_action : undefined}
                onAction={(action) => {
                  if (action === "find_care") navigate({ to: "/find-care" });
                  else if (action === "notes") navigate({ to: "/notes" });
                  else if (activeId != null) draftPlan.mutate(activeId);
                }}
              />
            ))}

            {pending && (
              <>
                <MessageBubble role="user" content={pending} pending />
                {streamed ? <MessageBubble role="assistant" content={streamed} /> : <TypingIndicator />}
              </>
            )}

            {error && (
              <Alert severity="error" onClose={() => setError(null)}>
                {error}
              </Alert>
            )}
            <div ref={bottomRef} />
          </Stack>
        </Box>

        {showCrisisBanner && (
          <Box sx={{ px: { xs: 1.5, sm: 3 }, pt: 1 }}>
            <CrisisBanner
              onDismiss={() => setDismissedRiskId(lastRiskyId ?? null)}
              therapists={careTeam.map((m) => m.therapist_name)}
            />
          </Box>
        )}
        <Composer
          value={draft}
          onChange={setDraft}
          onSend={() => handleSend()}
          disabled={sendMutation.isPending || notFound}
          autoFocusKey={activeId}
        />
      </Box>
      <PlanEditor
        open={!!planDraft}
        initial={planDraft}
        heading="Your plan"
        onClose={() => setPlanDraft(null)}
        onSaved={() => {
          setPlanDraft(null);
          navigate({ to: "/plans" });
        }}
      />
    </Box>
  );
};
