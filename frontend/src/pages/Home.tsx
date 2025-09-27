import { CheckBox, Label } from "@mui/icons-material";
import {
  Avatar,
  Box,
  Button,
  FormControlLabel,
  Input,
  Link,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";

export const Home = () => {
  const [isAuthenticated, setAuthenticated] = useState(true);

  return (
    <Box>
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          flexDirection: "column",
          justifyItems: "center",
          width: "500px",
          height: "500px",
        }}
      >
        <Typography mt={10} variant="h1">Welcome to Therapy</Typography>
        <img src="../src/assets/therapy.jpg" alt="Avatar" />
      </Box>
      {isAuthenticated && (
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#f5f5f5", // light gray background
          }}
        >
          <Paper
            elevation={6}
            sx={{ p: 4, borderRadius: 3, width: "100%", maxWidth: 400 }}
          >
            {/* login form here */}
            <Stack spacing={2}>
              <TextField
                type="text"
                placeholder="Enter Username"
                name="username"
                variant="filled"
                required
                fullWidth
              />
              <TextField
                type="password"
                placeholder="Enter Password"
                name="password"
                variant="filled"
                required
                fullWidth
              />
              <Button type="submit" variant="contained" fullWidth>
                Login
              </Button>
              <Stack direction="row" alignItems="center" spacing={1}>
                <FormControlLabel
                  control={<CheckBox />}
                  label={"Remember me"}
                />
              </Stack>
              <Box
                sx={{
                  backgroundColor: "#f1f1f1",
                  p: 2,
                  borderRadius: 1,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <Button type="button" variant="outlined">
                  Cancel
                </Button>
                <span>
                  <Link href="#">Forgot password?</Link>
                </span>
              </Box>
            </Stack>
          </Paper>
        </Box>
      )}
    </Box>
  );
};

export default Home;
