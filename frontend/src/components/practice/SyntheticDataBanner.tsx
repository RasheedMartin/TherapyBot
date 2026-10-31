import { Alert } from "@mui/material";
import { usePublicConfig } from "../../api/config";

/** Shown wherever clinical records can be entered, until the deployment is cleared for real patient data. */
export const SyntheticDataBanner = () => {
  const { data } = usePublicConfig();
  if (!data || data.phi_allowed) return null;
  return (
    <Alert severity="warning" variant="outlined" sx={{ borderRadius: 3 }}>
      <strong>Demo environment: use synthetic data only.</strong> Don't enter real client information until this
      deployment is approved for protected health information.
    </Alert>
  );
};
