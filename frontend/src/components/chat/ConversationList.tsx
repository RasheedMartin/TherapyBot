import { useState } from "react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  Skeleton,
  Typography,
} from "@mui/material";
import { Add, DeleteOutline } from "@mui/icons-material";
import type { Conversation } from "../../api/types";

interface ConversationListProps {
  conversations: Conversation[] | undefined;
  loading: boolean;
  activeId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
  onDelete: (id: number) => void;
}

const formatDate = (iso: string) => {
  const date = new Date(iso);
  const today = new Date();
  return date.toDateString() === today.toDateString()
    ? date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
    : date.toLocaleDateString([], { month: "short", day: "numeric" });
};

export const ConversationList = ({
  conversations,
  loading,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: ConversationListProps) => {
  const [pendingDelete, setPendingDelete] = useState<Conversation | null>(null);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Box sx={{ p: 2 }}>
        <Button fullWidth variant="contained" startIcon={<Add />} onClick={onNew}>
          New conversation
        </Button>
      </Box>
      <Typography variant="overline" color="text.secondary" sx={{ px: 2.5 }}>
        Recent
      </Typography>
      <List sx={{ flex: 1, overflowY: "auto", px: 1 }} dense>
        {loading &&
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} height={52} sx={{ mx: 1.5 }} />)}
        {!loading && conversations?.length === 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ px: 1.5, py: 1 }}>
            No conversations yet.
          </Typography>
        )}
        {conversations?.map((c) => (
          <ListItemButton
            key={c.id}
            selected={c.id === activeId}
            onClick={() => onSelect(c.id)}
            sx={{
              borderRadius: 2,
              mb: 0.5,
              pr: 6,
              "& .delete-btn": { opacity: 0 },
              "&:hover .delete-btn, & .delete-btn:focus-visible": { opacity: 1 },
              "@media (hover: none)": { "& .delete-btn": { opacity: 1 } },
            }}
          >
            <ListItemText
              primary={c.title || "New conversation"}
              secondary={`${c.therapy_type}, ${formatDate(c.updated_at)}`}
              slotProps={{
                primary: { noWrap: true, fontWeight: c.id === activeId ? 600 : 500 },
                secondary: { noWrap: true },
              }}
            />
            <IconButton
              className="delete-btn"
              size="small"
              aria-label={`Delete ${c.title || "conversation"}`}
              onClick={(e) => {
                e.stopPropagation();
                setPendingDelete(c);
              }}
              sx={{ position: "absolute", right: 8 }}
            >
              <DeleteOutline fontSize="small" />
            </IconButton>
          </ListItemButton>
        ))}
      </List>

      <Dialog open={!!pendingDelete} onClose={() => setPendingDelete(null)}>
        <DialogTitle>Delete this conversation?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            “{pendingDelete?.title || "New conversation"}” and all its messages will be permanently deleted.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingDelete(null)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => {
              if (pendingDelete) onDelete(pendingDelete.id);
              setPendingDelete(null);
            }}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
