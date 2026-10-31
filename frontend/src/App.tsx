import { Box } from "@mui/material";
import { Outlet, useRouterState } from "@tanstack/react-router";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";

function App() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isFullHeight = pathname.startsWith("/chat") || pathname.startsWith("/find-care");

  return (
    <Box sx={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}>
      <Navbar />
      <Box component="main" sx={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
        <Outlet />
      </Box>
      {!isFullHeight && <Footer />}
    </Box>
  );
}

export default App;
