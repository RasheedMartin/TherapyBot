import { useState } from "react";
import {
  AppBar,
  Avatar,
  Box,
  Button,
  Divider,
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Toolbar,
  Typography,
} from "@mui/material";
import {
  ChatBubbleOutline,
  ChecklistRtl,
  DescriptionOutlined,
  Logout,
  PersonOutline,
  PersonSearchOutlined,
  Spa,
} from "@mui/icons-material";
import { Link, useNavigate } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";

const NAV_LINKS = [
  { to: "/chat", label: "Chat", icon: <ChatBubbleOutline /> },
  { to: "/plans", label: "Plans", icon: <ChecklistRtl /> },
  { to: "/notes", label: "Notes", icon: <DescriptionOutlined /> },
  { to: "/find-care", label: "Find care", icon: <PersonSearchOutlined /> },
] as const;

export const Navbar = () => {
  const navigate = useNavigate();
  const { authenticated, user, logout } = useAuth();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const handleLogout = async () => {
    setAnchorEl(null);
    await logout();
    navigate({ to: "/" });
  };

  return (
    <AppBar position="sticky" sx={{ borderBottom: 1, borderColor: "divider", bgcolor: "background.paper" }}>
      <Toolbar sx={{ gap: 1 }}>
        <Box
          component={Link}
          to="/"
          sx={{ display: "flex", alignItems: "center", gap: 1, color: "text.primary", textDecoration: "none", mr: 2 }}
        >
          <Spa color="primary" />
          <Typography variant="h6" component="span" fontWeight={700} sx={{ display: { xs: authenticated ? "none" : "inline", sm: "inline" } }}>
            TherapyBot
          </Typography>
        </Box>

        <Box flexGrow={1} />

        {authenticated ? (
          <>
            {NAV_LINKS.map(({ to, label, icon }) => (
              <Button
                key={to}
                component={Link}
                to={to}
                color="inherit"
                activeProps={{ style: { fontWeight: 700 } }}
                sx={{ minWidth: 0, px: { xs: 1, sm: 2 } }}
                aria-label={label}
              >
                <Box component="span" sx={{ display: { xs: "inline-flex", sm: "none" } }}>
                  {icon}
                </Box>
                <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
                  {label}
                </Box>
              </Button>
            ))}
            <IconButton
              onClick={(e) => setAnchorEl(e.currentTarget)}
              aria-label="Account menu"
              aria-controls={anchorEl ? "account-menu" : undefined}
              aria-haspopup="true"
            >
              <Avatar sx={{ width: 32, height: 32, bgcolor: "primary.main", fontSize: 15 }}>
                {user?.display_name?.[0]?.toUpperCase() ?? "?"}
              </Avatar>
            </IconButton>
            <Menu
              id="account-menu"
              anchorEl={anchorEl}
              open={!!anchorEl}
              onClose={() => setAnchorEl(null)}
              anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
              transformOrigin={{ vertical: "top", horizontal: "right" }}
            >
              <Box sx={{ px: 2, py: 1 }}>
                <Typography variant="subtitle2">{user?.display_name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {user?.email}
                </Typography>
              </Box>
              <Divider />
              <MenuItem
                onClick={() => {
                  setAnchorEl(null);
                  navigate({ to: "/profile" });
                }}
              >
                <ListItemIcon>
                  <PersonOutline fontSize="small" />
                </ListItemIcon>
                Profile & settings
              </MenuItem>
              <MenuItem onClick={handleLogout}>
                <ListItemIcon>
                  <Logout fontSize="small" />
                </ListItemIcon>
                Sign out
              </MenuItem>
            </Menu>
          </>
        ) : (
          <>
            <Button component={Link} to="/login" color="inherit">
              Sign in
            </Button>
            <Button component={Link} to="/register" variant="contained">
              Get started
            </Button>
          </>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
