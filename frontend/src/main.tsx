import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "@fontsource-variable/noto-serif";
import "@/globals.css";

import { type ComponentType, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  createBrowserRouter,
  Navigate,
  Outlet,
  RouterProvider,
} from "react-router";

import { AppProviders } from "@/AppProviders";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { LoginScreen } from "@/components/screens/LoginScreen";
import { DashboardShell } from "@/components/shell/DashboardShell";

/** Gives a screen its own chunk, fetched the first time its route is visited. */
function lazyScreen<M>(
  load: () => Promise<M>,
  pick: (module: M) => ComponentType,
) {
  return async () => ({ Component: pick(await load()) });
}

const router = createBrowserRouter([
  {
    element: (
      <AppProviders>
        <Outlet />
      </AppProviders>
    ),
    children: [
      { path: "/login", element: <LoginScreen /> },
      {
        element: (
          <AuthGuard>
            <DashboardShell>
              <Outlet />
            </DashboardShell>
          </AuthGuard>
        ),
        children: [
          {
            index: true,
            lazy: lazyScreen(
              () => import("@/components/screens/OverviewScreen"),
              (module) => module.OverviewScreen,
            ),
          },
          {
            path: "channels",
            lazy: lazyScreen(
              () => import("@/components/screens/ChannelsScreen"),
              (module) => module.ChannelsScreen,
            ),
          },
          {
            path: "groups",
            lazy: lazyScreen(
              () => import("@/components/screens/GroupsScreen"),
              (module) => module.GroupsScreen,
            ),
          },
          {
            path: "requests",
            lazy: lazyScreen(
              () => import("@/components/screens/RequestsScreen"),
              (module) => module.RequestsScreen,
            ),
          },
          {
            path: "model-health",
            lazy: lazyScreen(
              () => import("@/components/screens/ModelHealthScreen"),
              (module) => module.ModelHealthScreen,
            ),
          },
          {
            path: "api-keys",
            lazy: lazyScreen(
              () => import("@/components/screens/ApiKeysScreen"),
              (module) => module.ApiKeysScreen,
            ),
          },
          {
            path: "cronjobs",
            lazy: lazyScreen(
              () => import("@/components/screens/CronjobsScreen"),
              (module) => module.CronjobsScreen,
            ),
          },
          {
            path: "backups",
            lazy: lazyScreen(
              () => import("@/components/screens/BackupsScreen"),
              (module) => module.BackupsScreen,
            ),
          },
          {
            path: "settings",
            lazy: lazyScreen(
              () => import("@/components/screens/SettingsScreen"),
              (module) => module.SettingsScreen,
            ),
          },
          { path: "*", element: <Navigate to="/" replace /> },
        ],
      },
    ],
  },
]);

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Missing #root element in index.html");

createRoot(rootElement).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
