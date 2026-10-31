import { Box, Container, Link, Stack, Typography } from "@mui/material";
import { RouterLink } from "./RouterLink";

export const Footer = () => (
  <Box component="footer" sx={{ borderTop: 1, borderColor: "divider", py: 4, mt: 6 }}>
    <Container maxWidth="md" sx={{ textAlign: "center" }}>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        TherapyBot is an AI support tool, not a replacement for a licensed professional.
      </Typography>
      <Typography variant="body2" color="text.secondary">
        In crisis? Call or text{" "}
        <Link href="tel:988" fontWeight={600}>
          988
        </Link>{" "}
        (US) or visit{" "}
        <Link href="https://findahelpline.com" target="_blank" rel="noopener noreferrer" fontWeight={600}>
          findahelpline.com
        </Link>
        .
      </Typography>
      <Stack direction="row" spacing={2} justifyContent="center" alignItems="center" mt={2}>
        <Typography variant="caption" color="text.secondary">
          © {new Date().getFullYear()} TherapyBot
        </Typography>
        <RouterLink to="/terms" variant="caption" color="text.secondary">
          Terms
        </RouterLink>
        <RouterLink to="/privacy" variant="caption" color="text.secondary">
          Privacy
        </RouterLink>
      </Stack>
    </Container>
  </Box>
);

export default Footer;
