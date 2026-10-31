import { Button, Container, Typography } from "@mui/material";
import { Link } from "@tanstack/react-router";

export const NotFound = () => (
  <Container maxWidth="sm" sx={{ py: 12, textAlign: "center" }}>
    <Typography variant="h3" component="h1" gutterBottom>
      Page not found
    </Typography>
    <Typography color="text.secondary" mb={4}>
      The page you're looking for doesn't exist or has moved.
    </Typography>
    <Button component={Link} to="/" variant="contained">
      Go home
    </Button>
  </Container>
);
