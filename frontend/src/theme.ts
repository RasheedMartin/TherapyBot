import { createTheme } from "@mui/material/styles";

const fontFamily = '"Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

export const theme = createTheme({
  cssVariables: { colorSchemeSelector: "media" },
  colorSchemes: {
    light: {
      palette: {
        primary: { main: "#2f6f62", light: "#5a9b8d", dark: "#1f4f45", contrastText: "#ffffff" },
        secondary: { main: "#c9835b" },
        background: { default: "#f6f4ef", paper: "#ffffff" },
        text: { primary: "#1f2a27", secondary: "#5b6764" },
        divider: "rgba(31, 42, 39, 0.1)",
      },
    },
    dark: {
      palette: {
        primary: { main: "#7cc3b3", light: "#a5dacd", dark: "#4f9a89", contrastText: "#0f1a17" },
        secondary: { main: "#e2a47f" },
        background: { default: "#111816", paper: "#18211e" },
        text: { primary: "#e6ece9", secondary: "#9fb0ab" },
        divider: "rgba(230, 236, 233, 0.1)",
      },
    },
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily,
    h1: { fontWeight: 700, letterSpacing: "-0.02em" },
    h2: { fontWeight: 700, letterSpacing: "-0.02em" },
    h3: { fontWeight: 700, letterSpacing: "-0.01em" },
    h4: { fontWeight: 700 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600 },
  },
  components: {
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { borderRadius: 999, paddingInline: 20 } },
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
  },
});
