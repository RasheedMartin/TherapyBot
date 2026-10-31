import { Avatar, Box, Button, Chip, Paper, Stack, Typography } from "@mui/material";
import {
  ArrowForward,
  ChecklistRtl,
  DescriptionOutlined,
  MenuBookOutlined,
  PersonSearchOutlined,
  Spa,
  WarningAmberRounded,
} from "@mui/icons-material";
import type { Message } from "../../api/types";
import Markdown from "react-markdown";
import { useRouter } from "@tanstack/react-router";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  isCrisis?: boolean;
  pending?: boolean;
  sources?: Message["sources"];
  /** A feature hand-off to offer under the reply, and what to do when it's chosen. */
  action?: Message["suggested_action"];
  onAction?: (action: NonNullable<Message["suggested_action"]>) => void;
}

const ACTIONS = {
  find_care: { label: "Find therapists near you", icon: <PersonSearchOutlined /> },
  plan: { label: "Turn this into a plan", icon: <ChecklistRtl /> },
  notes: { label: "Explain my therapist's notes", icon: <DescriptionOutlined /> },
} as const;

export const MessageBubble = ({ role, content, isCrisis, pending, sources, action, onAction }: MessageBubbleProps) => {
  const isUser = role === "user";
  const router = useRouter();

  return (
    <Box sx={{ display: "flex", gap: 1.5, justifyContent: isUser ? "flex-end" : "flex-start", opacity: pending ? 0.7 : 1 }}>
      {!isUser && (
        <Avatar sx={{ width: 32, height: 32, bgcolor: isCrisis ? "warning.main" : "primary.main", mt: 0.5 }}>
          {isCrisis ? <WarningAmberRounded fontSize="small" /> : <Spa fontSize="small" />}
        </Avatar>
      )}
      <Stack spacing={0.75} alignItems={isUser ? "flex-end" : "flex-start"} sx={{ maxWidth: { xs: "85%", md: "75%" } }}>
        <Paper
          elevation={0}
          sx={{
            px: 2,
            py: 1.5,
            borderRadius: 3,
            borderTopRightRadius: isUser ? 6 : undefined,
            borderTopLeftRadius: isUser ? undefined : 6,
            bgcolor: isUser ? "primary.main" : "background.paper",
            color: isUser ? "primary.contrastText" : "text.primary",
            border: isUser ? "none" : 1,
            borderColor: isCrisis ? "warning.main" : "divider",
            overflowWrap: "anywhere",
            "& p": { m: 0 },
            "& p + p, & ul, & ol": { mt: 1 },
            "& ul, & ol": { pl: 2.5, mb: 0 },
            "& li + li": { mt: 0.5 },
            "& a": { color: "inherit", fontWeight: 600 },
          }}
        >
          {isUser ? (
            <Typography variant="body1" sx={{ whiteSpace: "pre-wrap" }}>
              {content}
            </Typography>
          ) : (
            <Typography variant="body1" component="div">
              <Markdown
                components={{
                  a: ({ children, href }) =>
                    href?.startsWith("/") ? (
                      // In-app links (e.g. the bot suggesting Find care) navigate without leaving the app
                      <a
                        href={href}
                        onClick={(e) => {
                          e.preventDefault();
                          router.history.push(href);
                        }}
                      >
                        {children}
                      </a>
                    ) : (
                      <a href={href} target="_blank" rel="noopener noreferrer">
                        {children}
                      </a>
                    ),
                }}
              >
                {content}
              </Markdown>
            </Typography>
          )}
        </Paper>
        {action && onAction && (
          <Button
            size="small"
            variant="contained"
            startIcon={ACTIONS[action].icon}
            endIcon={<ArrowForward />}
            onClick={() => onAction(action)}
          >
            {ACTIONS[action].label}
          </Button>
        )}
        {!!sources?.length &&
          sources.map((s) => (
            <Chip
              key={s.url}
              component="a"
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              clickable
              size="small"
              variant="outlined"
              icon={<MenuBookOutlined />}
              label={`Read more: ${s.title} · ${s.source}`}
              sx={{ maxWidth: "100%" }}
            />
          ))}
      </Stack>
    </Box>
  );
};

export const TypingIndicator = () => (
  <Box sx={{ display: "flex", gap: 1.5 }} aria-live="polite" aria-label="TherapyBot is typing">
    <Avatar sx={{ width: 32, height: 32, bgcolor: "primary.main" }}>
      <Spa fontSize="small" />
    </Avatar>
    <Paper
      elevation={0}
      sx={{
        px: 2,
        py: 1.75,
        borderRadius: 3,
        borderTopLeftRadius: 6,
        border: 1,
        borderColor: "divider",
        display: "flex",
        gap: 0.75,
        alignItems: "center",
        "@keyframes typing": {
          "0%, 60%, 100%": { transform: "translateY(0)", opacity: 0.4 },
          "30%": { transform: "translateY(-4px)", opacity: 1 },
        },
      }}
    >
      {[0, 1, 2].map((i) => (
        <Box
          key={i}
          sx={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            bgcolor: "text.secondary",
            animation: "typing 1.2s infinite ease-in-out",
            animationDelay: `${i * 0.15}s`,
            "@media (prefers-reduced-motion: reduce)": { animation: "none" },
          }}
        />
      ))}
    </Paper>
  </Box>
);
