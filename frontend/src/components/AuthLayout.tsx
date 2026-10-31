import { Box, Paper, Stack, Typography } from "@mui/material";
import { Spa } from "@mui/icons-material";

interface AuthLayoutProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

/** Centered card shared by the login, register and password pages. */
export const AuthLayout = ({ title, subtitle, children, footer }: AuthLayoutProps) => (
  <Box sx={{ flex: 1, display: "grid", placeItems: "center", px: 2, py: { xs: 4, sm: 8 } }}>
    <Paper
      variant="outlined"
      sx={{ p: { xs: 3, sm: 5 }, width: "100%", maxWidth: 440, borderRadius: 4 }}
    >
      <Stack spacing={1} alignItems="center" textAlign="center" mb={3}>
        <Box
          sx={{
            width: 48,
            height: 48,
            borderRadius: "50%",
            display: "grid",
            placeItems: "center",
            bgcolor: "primary.main",
            color: "primary.contrastText",
            mb: 1,
          }}
        >
          <Spa />
        </Box>
        <Typography variant="h5" component="h1">
          {title}
        </Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </Stack>
      {children}
      {footer && (
        <Typography variant="body2" color="text.secondary" textAlign="center" mt={3}>
          {footer}
        </Typography>
      )}
    </Paper>
  </Box>
);
