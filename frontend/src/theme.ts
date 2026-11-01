import { createTheme } from "@mui/material/styles";

/*
 * Visual direction: a well-kept clinical record. Calm, precise and legible rather than a wellness-app look.
 * Cool paper white with ink text, one brand green, amber only for things that need attention, red only for
 * crisis. Source Serif 4 gives page titles the weight of a record; Public Sans keeps everything else plain
 * and readable. All text pairs below pass WCAG AA (contrast checked when the palette was set).
 */

const sans = '"Public Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
const serif = '"Source Serif 4", Georgia, "Times New Roman", serif';

// Brand green tonal scale (600 is the brand colour)
export const spruce = {
  50: "#EEF3F2",
  100: "#DEE7E5",
  200: "#B8CCC8",
  300: "#8EAFA7",
  400: "#608E83",
  500: "#43796C",
  600: "#2E6A5C",
  700: "#26574B",
  800: "#1E463D",
  900: "#17352E",
};

export const theme = createTheme({
  cssVariables: { colorSchemeSelector: "media" },
  colorSchemes: {
    light: {
      palette: {
        primary: { main: spruce[600], light: spruce[400], dark: spruce[800], contrastText: "#FFFFFF" },
        secondary: { main: spruce[800], contrastText: "#FFFFFF" },
        // Amber is for attention only: icons and borders at main (3:1 UI), text at dark (5.4:1 on its tint)
        warning: { main: "#B7791F", dark: "#8A5A12", light: "#FBF3E4", contrastText: "#FFFFFF" },
        error: { main: "#B42318", dark: "#8F1C13", light: "#FDECEA", contrastText: "#FFFFFF" },
        success: { main: spruce[600], contrastText: "#FFFFFF" },
        info: { main: "#2B5C8A", contrastText: "#FFFFFF" },
        background: { default: "#F7F8F7", paper: "#FFFFFF" },
        text: { primary: "#1B2321", secondary: "#5A6461" },
        divider: "rgba(27, 35, 33, 0.12)",
        action: { hover: "rgba(46, 106, 92, 0.06)", selected: "rgba(46, 106, 92, 0.1)" },
      },
    },
    dark: {
      palette: {
        primary: { main: "#7CC0AE", light: "#A6D6C9", dark: "#4F9A89", contrastText: "#0E1A17" },
        secondary: { main: "#A6D6C9", contrastText: "#0E1A17" },
        warning: { main: "#E0A445", dark: "#E0A445", light: "#2B2414", contrastText: "#1A1405" },
        error: { main: "#F0796E", dark: "#F0796E", light: "#2E1715", contrastText: "#1F0B09" },
        success: { main: "#7CC0AE", contrastText: "#0E1A17" },
        info: { main: "#8DB8E0", contrastText: "#0B1A27" },
        background: { default: "#101615", paper: "#172019" },
        text: { primary: "#E4EAE8", secondary: "#A3B0AC" },
        divider: "rgba(228, 234, 232, 0.12)",
      },
    },
  },
  // A small base unit, so sx radii form a hierarchy: 4 → 10px cards, 3 → 7.5px panels, 2 → 5px rows
  shape: { borderRadius: 2.5 },
  typography: {
    fontFamily: sans,
    // Page titles in the serif; section headings stay in the sans so the serif keeps its weight
    h1: { fontFamily: serif, fontWeight: 600, letterSpacing: "-0.015em" },
    h2: { fontFamily: serif, fontWeight: 600, letterSpacing: "-0.015em" },
    h3: { fontFamily: serif, fontWeight: 600, letterSpacing: "-0.01em" },
    h4: { fontFamily: serif, fontWeight: 600, letterSpacing: "-0.01em", lineHeight: 1.2 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600, fontSize: "1.0625rem", lineHeight: 1.4 },
    body1: { lineHeight: 1.6 },
    body2: { lineHeight: 1.55 },
    subtitle2: { fontWeight: 600 },
    // Small labels in sentence case: no tracked-out capitals
    overline: { textTransform: "none", letterSpacing: 0, fontWeight: 600, fontSize: "0.8125rem", lineHeight: 1.5 },
    button: { textTransform: "none", fontWeight: 600, letterSpacing: 0 },
  },
  components: {
    MuiButton: {
      defaultProps: { disableElevation: true },
      // Labels never break mid-button; crowded toolbars wrap whole buttons instead
      styleOverrides: { root: { borderRadius: 6, paddingInline: 16, whiteSpace: "nowrap" } },
    },
    MuiIconButton: {
      styleOverrides: { root: { borderRadius: 6 } },
    },
    MuiOutlinedInput: {
      styleOverrides: { root: { borderRadius: 6 } },
    },
    MuiAlert: {
      styleOverrides: { root: { borderRadius: 8 } },
    },
    MuiDialog: {
      styleOverrides: { paper: { borderRadius: 12 } },
    },
    MuiMenu: {
      styleOverrides: { paper: { borderRadius: 8 } },
    },
    MuiChip: {
      styleOverrides: { root: { borderRadius: 6, fontWeight: 500 } },
    },
    MuiPaper: {
      styleOverrides: { root: { backgroundImage: "none" } },
    },
    MuiTextField: {
      defaultProps: { fullWidth: true },
    },
    MuiAppBar: {
      defaultProps: { elevation: 0, color: "inherit" },
    },
    MuiLink: {
      styleOverrides: { root: { textUnderlineOffset: "0.18em" } },
    },
  },
});
