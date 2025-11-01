import { AppBar, Box, Button, IconButton, Toolbar } from "@mui/material";
import { Menu } from "@mui/icons-material";
import { useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../context/AuthContext";
import { useUser } from "../context/UserContext";

export const Navbar = () => {
  const navigate = useNavigate();
  const { authenticated, logout } = useAuth();
  const queryClient = useQueryClient();
  const { setUser } = useUser();

  const handleLogout = () => {
    logout();
    queryClient.clear();
    setUser(null);
    navigate({ to: "/login" });
  };

  const handleLoginLogout = () => {
    if (authenticated) {
      handleLogout();
    } else {
      navigate({ to: "/login" });
    }
  };

  return (
    <AppBar>
      <Toolbar>
        <IconButton
          size="large"
          edge="start"
          color="inherit"
          aria-label="menu"
          sx={{ mr: 2 }}
        >
          <Menu />
        </IconButton>
        <Button
          onClick={() => {
            navigate({ to: "/" });
          }}
          color={"inherit"}
        >
          {" "}
          Therapy Bot
        </Button>
        <Button
          color="inherit"
          onClick={() => navigate({ to: "/get-started" })}
        >
          Get Started
        </Button>
        <Box flexGrow={1} />
        <Button color="inherit" onClick={handleLoginLogout}>
          {authenticated ? "Logout" : "Login"}
        </Button>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
