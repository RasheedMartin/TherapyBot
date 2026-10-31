import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Typography,
  useColorScheme,
} from "@mui/material";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AxiosError } from "axios";
import api, { getErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { RouterLink } from "./RouterLink";

interface GoogleIdentity {
  accounts: {
    id: {
      initialize: (config: { client_id: string; callback: (r: { credential: string }) => void }) => void;
      renderButton: (el: HTMLElement, options: Record<string, unknown>) => void;
    };
  };
}

declare global {
  interface Window {
    google?: GoogleIdentity;
  }
}

const GSI_SRC = "https://accounts.google.com/gsi/client";

const loadGoogleScript = () =>
  new Promise<GoogleIdentity>((resolve, reject) => {
    if (window.google) return resolve(window.google);
    let script = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    if (!script) {
      script = document.createElement("script");
      script.src = GSI_SRC;
      script.async = true;
      document.head.appendChild(script);
    }
    script.addEventListener("load", () => (window.google ? resolve(window.google) : reject(new Error("GSI missing"))));
    script.addEventListener("error", () => reject(new Error("Couldn't load Google sign-in")));
  });

type GoogleResponse = { access: string; refresh: string; created: boolean };

/** "Continue with Google" button plus the consent step for first-time Google users. Renders nothing if not configured. */
export const GoogleSignIn = () => {
  const { acceptTokens } = useAuth();
  const { mode, systemMode } = useColorScheme();
  const buttonRef = useRef<HTMLDivElement>(null);
  const [pendingCredential, setPendingCredential] = useState<string | null>(null);
  const [agreed, setAgreed] = useState(false);

  const config = useQuery({
    queryKey: ["public-config"],
    queryFn: async () => (await api.get<{ google_client_id: string | null }>("config/")).data,
    staleTime: Infinity,
  });
  const clientId = config.data?.google_client_id;

  const signIn = useMutation({
    mutationFn: async (body: { credential: string; confirm_age?: boolean; accept_terms?: boolean }) =>
      (await api.post<GoogleResponse>("auth/google/", body)).data,
    onSuccess: (data) => {
      setPendingCredential(null);
      acceptTokens(data.access, data.refresh); // RequireGuest then sends the user onward
    },
    onError: (err, body) => {
      if (err instanceof AxiosError && err.response?.data?.consent_required) setPendingCredential(body.credential);
    },
  });

  const dark = (mode === "system" ? systemMode : mode) === "dark";
  useEffect(() => {
    if (!clientId || !buttonRef.current) return;
    let cancelled = false;
    loadGoogleScript()
      .then((google) => {
        if (cancelled || !buttonRef.current) return;
        google.accounts.id.initialize({ client_id: clientId, callback: ({ credential }) => signIn.mutate({ credential }) });
        google.accounts.id.renderButton(buttonRef.current, {
          theme: dark ? "filled_black" : "outline",
          size: "large",
          shape: "pill",
          text: "continue_with",
          width: buttonRef.current.offsetWidth || 320,
        });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // signIn.mutate is stable; re-render the button only when the client or theme changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, dark]);

  if (!clientId) return null;
  const consentError = signIn.error instanceof AxiosError && signIn.error.response?.data?.consent_required;

  return (
    <>
      <Divider sx={{ my: 3 }}>
        <Typography variant="body2" color="text.secondary">
          or
        </Typography>
      </Divider>
      <Box ref={buttonRef} sx={{ display: "flex", justifyContent: "center", minHeight: 44 }} />
      {signIn.isError && !consentError && !pendingCredential && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {getErrorMessage(signIn.error)}
        </Alert>
      )}

      <Dialog open={!!pendingCredential} onClose={() => setPendingCredential(null)} maxWidth="xs" fullWidth>
        <DialogTitle>One more step</DialogTitle>
        <DialogContent>
          <Typography color="text.secondary" mb={2}>
            Before we create your account:
          </Typography>
          <FormControlLabel
            control={<Checkbox checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />}
            label={
              <Typography variant="body2">
                I'm 18 or older and agree to the <RouterLink to="/terms">Terms</RouterLink> and{" "}
                <RouterLink to="/privacy">Privacy Policy</RouterLink>.
              </Typography>
            }
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingCredential(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!agreed || signIn.isPending}
            onClick={() =>
              pendingCredential && signIn.mutate({ credential: pendingCredential, confirm_age: true, accept_terms: true })
            }
          >
            Create account
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};
