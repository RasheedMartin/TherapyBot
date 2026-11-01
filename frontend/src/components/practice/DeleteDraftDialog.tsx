import { Alert, Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from "@mui/material";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../../api/client";

/**
 * Confirm and delete a draft note. Only the draft's author can delete it, and signed notes can't be
 * deleted at all; the server enforces both and its message is shown if it refuses.
 */
export const DeleteDraftDialog = ({
  draft,
  onClose,
  onDeleted,
}: {
  draft: { id: number; client_id: number; title: string } | null;
  onClose: () => void;
  onDeleted?: () => void;
}) => {
  const queryClient = useQueryClient();
  const discard = useMutation({
    mutationFn: (d: { id: number; client_id: number }) => api.delete(`practice/clients/${d.client_id}/documents/${d.id}/`),
    onSuccess: (_, d) => {
      queryClient.removeQueries({ queryKey: ["document", d.client_id, d.id] });
      queryClient.invalidateQueries({ queryKey: ["timeline", d.client_id] });
      queryClient.invalidateQueries({ queryKey: ["practice-overview"] });
      onClose();
      onDeleted?.();
    },
  });

  return (
    <Dialog open={!!draft} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Delete this draft?</DialogTitle>
      <DialogContent>
        <DialogContentText>
          “{draft?.title}” will be deleted for good. It was never signed, so nothing in the client's signed record changes.
        </DialogContentText>
        {discard.isError && <Alert severity="error" sx={{ mt: 2 }}>{getErrorMessage(discard.error)}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Keep it</Button>
        <Button color="error" variant="contained" disabled={discard.isPending || !draft} onClick={() => draft && discard.mutate(draft)}>
          Delete draft
        </Button>
      </DialogActions>
    </Dialog>
  );
};
