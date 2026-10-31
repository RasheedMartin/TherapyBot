import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");

  return {
    plugins: [
      react({
        babel: {
          plugins: [["babel-plugin-react-compiler"]],
        },
      }),
    ],
    build: {
      rollupOptions: {
        output: {
          // Vendor chunks change rarely, so browsers keep them cached across deploys
          manualChunks: {
            mui: ["@mui/material", "@mui/icons-material", "@emotion/react", "@emotion/styled"],
            tanstack: ["@tanstack/react-router", "@tanstack/react-query"],
            markdown: ["react-markdown"],
            map: ["leaflet", "react-leaflet"],
            charts: ["@mui/x-charts"],
          },
        },
      },
    },
    server: {
      port: 5174,
      // In dev, leave VITE_API_URL unset and requests are proxied to Django.
      // Set API_PROXY_TARGET (e.g. in .env.local) if Django isn't on port 8000.
      proxy: {
        "/api": env.API_PROXY_TARGET || "http://localhost:8000",
      },
    },
  };
});
