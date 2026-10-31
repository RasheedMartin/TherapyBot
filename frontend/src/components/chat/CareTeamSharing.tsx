import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Switch,
  Typography,
} from "@mui/material";
import { LockOutlined, PeopleOutline } from "@mui/icons-material";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";
import type { ConversationDetail } from "../../api/types";
import { LinkButton } from "../RouterLink";
import { useActiveCareTeam } from "./careTeam";

/** Header chip: whether this conversation is shared with the care team, and the control to change it. */
export const CareTeamSharing = ({ conversation }: { conversation: ConversationDetail }) => {
  const queryClient = useQueryClient();
  const team = useActiveCareTeam();
  const [open, setOpen] = useState(false);
  const toggle = useMutation({
    mutationFn: async (shared: boolean) =>
      (await api.patch<ConversationDetail>(`conversations/${conversation.id}/`, { shared_with_care_team: shared })).data,
    onSuccess: (updated) => {
      queryClient.setQueryData<ConversationDetail>(["conversation", conversation.id], (old) =>
        old ? { ...old, shared_with_care_team: updated.shared_with_care_team } : old,
      );
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
  if (team.length === 0) return null;

  const names = team.map((m) => m.therapist_name).join(" and ");
  const sharesChat = team.some((m) => m.share_chat_summaries || m.share_raw_chat);
  const shared = sharesChat && conversation.shared_with_care_team;
  const what = team.some((m) => m.share_raw_chat) ? "this conversation" : "a summary of this conversation";

  return (
    <>
      <Chip
        size="small"
        icon={shared ? <PeopleOutline /> : <LockOutlined />}
        label={shared ? "Shared with your therapist" : "Private"}
        onClick={() => setOpen(true)}
        variant="outlined"
      />
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>What {names} can see</DialogTitle>
        <DialogContent>
          {sharesChat ? (
            <>
              <FormControlLabel
                control={
                  <Switch
                    checked={conversation.shared_with_care_team}
                    disabled={toggle.isPending}
                    onChange={(e) => toggle.mutate(e.target.checked)}
                  />
                }
                label={`Share ${what} with your therapist`}
              />
              <Typography variant="body2" color="text.secondary" mt={1}>
                Turn this off to keep this conversation just for you. Your other conversations aren't affected.
              </Typography>
            </>
          ) : (
            <Typography>
              You've chosen not to share conversations, so your therapist doesn't see what you write here. You can
              change that in your profile.
            </Typography>
          )}
          <Alert severity="info" sx={{ mt: 2 }}>
            Safety alerts are always shared: if a message suggests you may be at risk of harming yourself, your
            therapist sees a flag, but not right away. In an emergency call 911, or call or text 988.
          </Alert>
          {shared && conversation.care_summary && (
            <Box mt={2}>
              <Typography variant="subtitle2" gutterBottom>The latest summary your therapist saw</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.6 }}>{conversation.care_summary}</Typography>
            </Box>
          )}
          {toggle.isError && <Alert severity="error" sx={{ mt: 2 }}>{getErrorMessage(toggle.error)}</Alert>}
        </DialogContent>
        <DialogActions>
          <LinkButton to="/profile" onClick={() => setOpen(false)}>Sharing settings</LinkButton>
          <Button variant="contained" onClick={() => setOpen(false)}>Done</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};
