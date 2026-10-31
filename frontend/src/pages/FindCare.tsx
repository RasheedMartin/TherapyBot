import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  InputAdornment,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  Tab,
  Tabs,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import { DeleteOutline, MapOutlined, MyLocation, Phone, RecordVoiceOver, Search, ViewList } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearch } from "@tanstack/react-router";
import api, { getErrorMessage } from "../api/client";
import {
  OUTREACH_STATUSES,
  PROVIDER_TYPES,
  type OutreachStatus,
  type Profile,
  type Provider,
  type ProviderSearchResult,
  type ProviderType,
  type SavedProvider,
} from "../api/types";
import { CallScriptDialog } from "../components/care/CallScriptDialog";
import { CareResources } from "../components/care/CareResources";
import { ProviderCard } from "../components/care/ProviderCard";
import { ProviderMap } from "../components/care/ProviderMap";

const ALL_TYPES = PROVIDER_TYPES.map((t) => t.key);
const DEFAULT_TYPES: ProviderType[] = ["psychologist", "counselor", "social_worker", "marriage_family"];

const milesBetween = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) => {
  const rad = (d: number) => (d * Math.PI) / 180;
  const h =
    Math.sin(rad(b.lat - a.lat) / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lng - a.lng) / 2) ** 2;
  return 3958.8 * 2 * Math.asin(Math.sqrt(h));
};

const toProvider = (s: SavedProvider): Provider => ({ ...s.details, npi: s.npi });

export const FindCarePage = () => {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const queryClient = useQueryClient();

  const profileQuery = useQuery({
    queryKey: ["profile"],
    queryFn: async () => (await api.get<Profile>("profile/")).data,
  });
  const profile = profileQuery.data;

  const [zipInput, setZipInput] = useState("");
  const [zip, setZip] = useState("");
  const [types, setTypes] = useState<Set<ProviderType>>(new Set(DEFAULT_TYPES));
  const initialTab = useSearch({ from: "/find-care" }).tab;
  const [tab, setTab] = useState<"results" | "shortlist">(initialTab ?? "results");
  const [mobileView, setMobileView] = useState<"list" | "map">("list");
  const [selected, setSelected] = useState<string | null>(null);
  const [scriptFor, setScriptFor] = useState<Provider | null>(null);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const cardRefs = useRef(new Map<string, HTMLDivElement>());

  // Start from the ZIP saved in the profile
  useEffect(() => {
    if (profile?.zip_code && !zip) {
      setZipInput(profile.zip_code);
      setZip(profile.zip_code);
    }
  }, [profile?.zip_code, zip]);

  const search = useQuery({
    queryKey: ["providers", zip],
    queryFn: async () =>
      (await api.get<ProviderSearchResult>("providers/", { params: { zip, types: ALL_TYPES.join(",") } })).data,
    enabled: /^\d{5}$/.test(zip),
    staleTime: 10 * 60_000,
    retry: false,
  });

  const savedQuery = useQuery({
    queryKey: ["saved-providers"],
    queryFn: async () => (await api.get<SavedProvider[]>("saved-providers/")).data,
  });
  const savedByNpi = useMemo(() => new Map((savedQuery.data ?? []).map((s) => [s.npi, s])), [savedQuery.data]);

  const distance = (p: Provider) =>
    userLocation && p.lat != null && p.lng != null ? milesBetween(userLocation, { lat: p.lat, lng: p.lng }) : null;

  const results = useMemo(() => {
    const list = (search.data?.providers ?? []).filter((p) => types.has(p.type));
    if (!userLocation) return list;
    const d = (p: Provider) =>
      p.lat != null && p.lng != null ? milesBetween(userLocation, { lat: p.lat, lng: p.lng }) : Infinity;
    return [...list].sort((a, b) => d(a) - d(b));
  }, [search.data, types, userLocation]);

  const shortlist = savedQuery.data ?? [];
  const mapProviders = tab === "shortlist" ? shortlist.map(toProvider) : results;

  const invalidateSaved = () => queryClient.invalidateQueries({ queryKey: ["saved-providers"] });
  const save = useMutation({
    mutationFn: (p: Provider) => {
      const { npi, ...details } = p;
      return api.post<SavedProvider>("saved-providers/", { npi, details });
    },
    onSuccess: invalidateSaved,
  });
  const update = useMutation({
    mutationFn: ({ id, ...data }: { id: number; status?: OutreachStatus; notes?: string }) =>
      api.patch(`saved-providers/${id}/`, data),
    onSuccess: () => {
      invalidateSaved();
      // Contacting a provider can complete a "call a therapist" plan step
      queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`saved-providers/${id}/`),
    onSuccess: invalidateSaved,
  });

  const toggleSave = (p: Provider) => {
    const existing = savedByNpi.get(p.npi);
    if (existing) remove.mutate(existing.id);
    else save.mutate(p);
  };

  const markContacted = (p: Provider) => {
    const existing = savedByNpi.get(p.npi);
    if (existing) update.mutate({ id: existing.id, status: "contacted" });
    else {
      const { npi, ...details } = p;
      api.post<SavedProvider>("saved-providers/", { npi, details }).then((res) => {
        update.mutate({ id: res.data.id, status: "contacted" });
      });
    }
  };

  const selectFromMap = (npi: string) => {
    setSelected(npi);
    if (!isDesktop) setMobileView("list");
    // Wait for the list to render (it may have been hidden on mobile)
    setTimeout(() => cardRefs.current.get(npi)?.scrollIntoView({ behavior: "smooth", block: "center" }), 50);
  };

  const locate = () => {
    setLocationError(null);
    if (!navigator.geolocation) {
      setLocationError("Your browser doesn't support location.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => setLocationError("Couldn't get your location. Check your browser's permission settings."),
      { enableHighAccuracy: false, timeout: 10_000 },
    );
  };

  const toggleType = (t: ProviderType) =>
    setTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t) && next.size > 1) next.delete(t);
      else next.add(t);
      return next;
    });

  const searchBar = (
    <Box
      component="form"
      onSubmit={(e) => {
        e.preventDefault();
        setSelected(null);
        setTab("results");
        setZip(zipInput.trim());
      }}
    >
      <Stack direction="row" spacing={1}>
        <TextField
          size="small"
          label="ZIP code"
          value={zipInput}
          onChange={(e) => setZipInput(e.target.value.replace(/\D/g, "").slice(0, 5))}
          inputProps={{ inputMode: "numeric" }}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <Tooltip title="Sort by distance from me">
                  <IconButton size="small" onClick={locate} aria-label="Use my location" edge="end">
                    <MyLocation fontSize="small" color={userLocation ? "primary" : "inherit"} />
                  </IconButton>
                </Tooltip>
              </InputAdornment>
            ),
          }}
        />
        <Button type="submit" variant="contained" startIcon={<Search />} disabled={!/^\d{5}$/.test(zipInput)}>
          Search
        </Button>
      </Stack>
      <Stack direction="row" spacing={0.75} mt={1.5} flexWrap="wrap" useFlexGap>
        {PROVIDER_TYPES.map((t) => {
          const count = search.data?.providers.filter((p) => p.type === t.key).length;
          return (
            <Chip
              key={t.key}
              size="small"
              label={count != null ? `${t.label} (${count})` : t.label}
              color={types.has(t.key) ? "primary" : "default"}
              variant={types.has(t.key) ? "filled" : "outlined"}
              onClick={() => toggleType(t.key)}
            />
          );
        })}
      </Stack>
      {locationError && (
        <Alert severity="warning" sx={{ mt: 1.5 }} onClose={() => setLocationError(null)}>
          {locationError}
        </Alert>
      )}
    </Box>
  );

  const resultsList = (
    <Stack spacing={1.5}>
      {!zip && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 3, textAlign: "center" }}>
          <Typography variant="h6" gutterBottom>
            Find a therapist near you
          </Typography>
          <Typography color="text.secondary">
            Enter your ZIP code to see licensed mental health providers in your area.
          </Typography>
        </Paper>
      )}
      {search.isLoading && Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} variant="rounded" height={150} />)}
      {search.isError && <Alert severity="error">{getErrorMessage(search.error)}</Alert>}
      {search.data && (
        <Typography variant="body2" color="text.secondary">
          {results.length} providers {search.data.widened ? `in the ${zip.slice(0, 3)}xx area` : `in ${zip}`}
          {userLocation ? ", nearest first" : ""}.
        </Typography>
      )}
      {search.data && results.length === 0 && (
        <Alert severity="info">No providers match these filters. Try selecting more provider types.</Alert>
      )}
      {results.map((p) => (
        <ProviderCard
          key={p.npi}
          ref={(el) => {
            if (el) cardRefs.current.set(p.npi, el);
            else cardRefs.current.delete(p.npi);
          }}
          provider={p}
          selected={p.npi === selected}
          saved={savedByNpi.has(p.npi)}
          distanceMiles={distance(p)}
          onSelect={() => setSelected(p.npi)}
          onToggleSave={() => toggleSave(p)}
          onCallScript={() => setScriptFor(p)}
        />
      ))}
      {search.data && (
        <Typography variant="caption" color="text.secondary">
          Listings come from the federal NPI Registry of licensed providers. They don't show availability or insurance,
          so call to confirm. Being listed is not an endorsement.
        </Typography>
      )}
      <CareResources zip={zip} />
    </Stack>
  );

  const shortlistView = (
    <Stack spacing={1.5}>
      {shortlist.length === 0 && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 3, textAlign: "center" }}>
          <Typography color="text.secondary">
            Save providers with the bookmark icon to track who you've contacted.
          </Typography>
        </Paper>
      )}
      {shortlist.map((s) => (
        <Paper
          key={s.id}
          ref={(el: HTMLDivElement | null) => {
            if (el) cardRefs.current.set(s.npi, el);
          }}
          variant="outlined"
          onClick={() => setSelected(s.npi)}
          sx={{ p: 2, borderRadius: 3, borderColor: s.npi === selected ? "primary.main" : "divider", cursor: "pointer" }}
        >
          <Stack direction="row" alignItems="flex-start" spacing={1}>
            <Box flex={1} minWidth={0}>
              <Typography fontWeight={600}>
                {s.details.name}
                {s.details.credential && `, ${s.details.credential}`}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {s.details.specialty} · {s.details.city}, {s.details.state}
              </Typography>
            </Box>
            <IconButton size="small" aria-label="Remove from shortlist" onClick={() => remove.mutate(s.id)}>
              <DeleteOutline fontSize="small" />
            </IconButton>
          </Stack>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} mt={1.5} onClick={(e) => e.stopPropagation()}>
            <TextField
              select
              size="small"
              label="Status"
              value={s.status}
              onChange={(e) => update.mutate({ id: s.id, status: e.target.value as OutreachStatus })}
              sx={{ minWidth: 200 }}
            >
              {OUTREACH_STATUSES.map((o) => (
                <MenuItem key={o.value} value={o.value}>
                  {o.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              size="small"
              label="Notes"
              placeholder="e.g. Left a voicemail Tuesday"
              defaultValue={s.notes}
              onBlur={(e) => e.target.value !== s.notes && update.mutate({ id: s.id, notes: e.target.value })}
            />
          </Stack>
          <Stack direction="row" spacing={1} mt={1.5} onClick={(e) => e.stopPropagation()}>
            {s.details.phone && (
              <Button size="small" variant="contained" startIcon={<Phone />} href={`tel:${s.details.phone}`}>
                {s.details.phone}
              </Button>
            )}
            <Button size="small" variant="outlined" startIcon={<RecordVoiceOver />} onClick={() => setScriptFor(toProvider(s))}>
              What to say
            </Button>
          </Stack>
        </Paper>
      ))}
    </Stack>
  );

  const listPanel = (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: 0, height: "100%" }}>
      <Box sx={{ p: 2, pb: 0 }}>
        {searchBar}
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mt: 1 }}>
          <Tab value="results" label="Results" />
          <Tab
            value="shortlist"
            label={
              <Badge badgeContent={shortlist.length} color="secondary" sx={{ "& .MuiBadge-badge": { right: -12 } }}>
                My shortlist
              </Badge>
            }
          />
        </Tabs>
      </Box>
      <Box sx={{ flex: 1, overflowY: "auto", p: 2, borderTop: 1, borderColor: "divider" }}>
        {tab === "results" ? resultsList : shortlistView}
      </Box>
    </Box>
  );

  const map = (
    <Box sx={{ position: "relative", height: "100%" }}>
      <ProviderMap
        providers={mapProviders}
        center={search.data?.center ?? null}
        selected={selected}
        saved={new Set(savedByNpi.keys())}
        userLocation={userLocation}
        onSelect={selectFromMap}
      />
      {search.isFetching && (
        <Paper sx={{ position: "absolute", top: 12, left: "50%", transform: "translateX(-50%)", px: 2, py: 1, zIndex: 1000, display: "flex", gap: 1, alignItems: "center", borderRadius: 999 }}>
          <CircularProgress size={16} /> <Typography variant="body2">Searching…</Typography>
        </Paper>
      )}
    </Box>
  );

  return (
    <Box sx={{ height: { xs: "calc(100dvh - 56px)", sm: "calc(100dvh - 64px)" }, display: "flex", flexDirection: "column" }}>
      {isDesktop ? (
        <Box sx={{ flex: 1, display: "grid", gridTemplateColumns: "440px 1fr", minHeight: 0 }}>
          <Box sx={{ borderRight: 1, borderColor: "divider", minHeight: 0, bgcolor: "background.paper" }}>{listPanel}</Box>
          {map}
        </Box>
      ) : (
        <>
          <Box sx={{ flex: 1, minHeight: 0 }}>{mobileView === "list" ? listPanel : map}</Box>
          <Box sx={{ p: 1, borderTop: 1, borderColor: "divider", display: "flex", justifyContent: "center" }}>
            <ToggleButtonGroup size="small" exclusive value={mobileView} onChange={(_, v) => v && setMobileView(v)}>
              <ToggleButton value="list">
                <ViewList fontSize="small" sx={{ mr: 0.5 }} /> List
              </ToggleButton>
              <ToggleButton value="map">
                <MapOutlined fontSize="small" sx={{ mr: 0.5 }} /> Map
              </ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </>
      )}
      <CallScriptDialog
        provider={scriptFor}
        profile={profile}
        onClose={() => setScriptFor(null)}
        onLogCall={() => scriptFor && markContacted(scriptFor)}
      />
    </Box>
  );
};
