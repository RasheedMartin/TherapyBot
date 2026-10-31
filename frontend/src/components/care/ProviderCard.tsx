import { forwardRef } from "react";
import { Box, Button, Chip, IconButton, Paper, Stack, Tooltip, Typography } from "@mui/material";
import { Bookmark, BookmarkBorder, Directions, Phone, RecordVoiceOver } from "@mui/icons-material";
import type { Provider } from "../../api/types";

interface ProviderCardProps {
  provider: Provider;
  selected: boolean;
  saved: boolean;
  distanceMiles: number | null;
  onSelect: () => void;
  onToggleSave: () => void;
  onCallScript: () => void;
}

const directionsUrl = (p: Pick<Provider, "street" | "city" | "state" | "zip">) =>
  `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${p.street}, ${p.city}, ${p.state} ${p.zip}`)}`;

export const ProviderCard = forwardRef<HTMLDivElement, ProviderCardProps>(
  ({ provider: p, selected, saved, distanceMiles, onSelect, onToggleSave, onCallScript }, ref) => (
    <Paper
      ref={ref}
      variant="outlined"
      onClick={onSelect}
      sx={{
        p: 2,
        borderRadius: 3,
        cursor: "pointer",
        borderColor: selected ? "primary.main" : "divider",
        boxShadow: selected ? (t) => `0 0 0 1px ${t.palette.primary.main}` : "none",
        transition: "border-color .15s",
        "&:hover": { borderColor: "primary.light" },
      }}
    >
      <Stack direction="row" spacing={1} alignItems="flex-start">
        <Box flex={1} minWidth={0}>
          <Typography variant="subtitle1" fontWeight={600} lineHeight={1.3}>
            {p.name}
            {p.credential && (
              <Typography component="span" variant="body2" color="text.secondary">
                , {p.credential}
              </Typography>
            )}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {p.specialty}
            {p.is_organization && " · Practice"}
          </Typography>
        </Box>
        <Tooltip title={saved ? "Remove from shortlist" : "Save to shortlist"}>
          <IconButton
            size="small"
            color={saved ? "secondary" : "default"}
            aria-label={saved ? "Remove from shortlist" : "Save to shortlist"}
            onClick={(e) => {
              e.stopPropagation();
              onToggleSave();
            }}
          >
            {saved ? <Bookmark /> : <BookmarkBorder />}
          </IconButton>
        </Tooltip>
      </Stack>
      <Typography variant="body2" mt={1}>
        {p.street}, {p.city}, {p.state} {p.zip}
      </Typography>
      <Stack direction="row" spacing={1} mt={1} flexWrap="wrap" useFlexGap>
        {distanceMiles != null && <Chip size="small" label={`${distanceMiles.toFixed(1)} mi`} />}
        {p.license_state && <Chip size="small" variant="outlined" label={`Licensed in ${p.license_state}`} />}
      </Stack>
      <Stack direction="row" spacing={1} mt={1.5} flexWrap="wrap" useFlexGap onClick={(e) => e.stopPropagation()}>
        {p.phone && (
          <Button size="small" variant="contained" startIcon={<Phone />} href={`tel:${p.phone}`}>
            {p.phone}
          </Button>
        )}
        <Button size="small" variant="outlined" startIcon={<RecordVoiceOver />} onClick={onCallScript}>
          What to say
        </Button>
        <Button size="small" startIcon={<Directions />} href={directionsUrl(p)} target="_blank" rel="noopener noreferrer">
          Directions
        </Button>
      </Stack>
    </Paper>
  ),
);
