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
  CalendarMonthOutlined,
  ChatBubbleOutline,
  ChecklistRtl,
  DescriptionOutlined,
  FactCheckOutlined,
  GroupsOutlined,
  HomeOutlined,
  Logout,
  PersonOutline,
  PersonSearchOutlined,
  Spa,
} from "@mui/icons-material";
import { Link, useNavigate } from "@tanstack/react-router";
import { useReturnHere } from "./returnTo";
import { LinkButton } from "./RouterLink";
import { useAuth } from "../context/AuthContext";
import { useActiveCareTeam } from "./chat/careTeam";

// "Home" matches only its own page; the others stay highlighted on the pages beneath them
const CLIENT_LINKS = [
  { to: "/", label: "Home", icon: <HomeOutlined />, exact: true },
  { to: "/my-therapist", label: "My therapist", icon: <PersonOutline /> },
  { to: "/chat", label: "Chat", icon: <ChatBubbleOutline /> },
  { to: "/plans", label: "Plans", icon: <ChecklistRtl /> },
  { to: "/notes", label: "Notes", icon: <DescriptionOutlined /> },
  { to: "/find-care", label: "Find care", icon: <PersonSearchOutlined /> },
] as const;

const THERAPIST_LINKS = [
  { to: "/practice", label: "Home", icon: <HomeOutlined />, exact: true },
  { to: "/practice/schedule", label: "Schedule", icon: <CalendarMonthOutlined /> },
  { to: "/practice/clients", label: "Clients", icon: <GroupsOutlined /> },
  { to: "/practice/notes", label: "Notes", icon: <DescriptionOutlined /> },
];

export const Navbar = () => {
  const returnHere = useReturnHere();
  const navigate = useNavigate();
  const { authenticated, user, logout } = useAuth();
  // Clients in care get a page for their therapist; everyone else keeps Find care in that spot
  const inCare = useActiveCareTeam(authenticated && user?.role !== "therapist" && !!user?.email_verified).length > 0;
  const clientLinks = CLIENT_LINKS.filter((l) => (l.to === "/my-therapist" ? inCare : true));
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
            {(user?.role === "therapist" ? THERAPIST_LINKS : clientLinks).map((link) => ({ ...link, exact: "exact" in link && link.exact })).map(({ to, label, icon, exact }) => (
              <Button
                key={to}
                component={Link}
                to={to}
                color="inherit"
                activeOptions={{ exact: !!exact }}
                activeProps={{ style: { fontWeight: 700 }, "aria-current": "page" }}
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
              {user?.role === "therapist" && (
                <MenuItem
                  onClick={() => {
                    setAnchorEl(null);
                    navigate({ to: "/practice/templates" });
                  }}
                >
                  <ListItemIcon>
                    <FactCheckOutlined fontSize="small" />
                  </ListItemIcon>
                  Screening templates
                </MenuItem>
              )}
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
            <LinkButton to="/login" search={returnHere} color="inherit">
              Sign in
            </LinkButton>
            <LinkButton to="/register" search={returnHere} variant="contained">
              Get started
            </LinkButton>
          </>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
