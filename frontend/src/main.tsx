import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
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
import { lazyComponent } from "@/lib/lazyComponent";

function lazyScreen<M>(
  load: () => Promise<M>,
  pick: (module: M) => ComponentType,
) {
  const Screen = lazyComponent(() => load().then(pick));
  return <Screen />;
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
            element: lazyScreen(
              () => import("@/components/screens/OverviewScreen"),
              (module) => module.OverviewScreen,
            ),
          },
          {
            path: "channels",
            element: lazyScreen(
              () => import("@/components/screens/ChannelsScreen"),
              (module) => module.ChannelsScreen,
            ),
          },
          {
            path: "groups",
            element: lazyScreen(
              () => import("@/components/screens/GroupsScreen"),
              (module) => module.GroupsScreen,
            ),
          },
          {
            path: "billing",
            element: lazyScreen(
              () => import("@/components/screens/ModelPricesScreen"),
              (module) => module.ModelPricesScreen,
            ),
          },
          {
            path: "requests",
            element: lazyScreen(
              () => import("@/components/screens/RequestsScreen"),
              (module) => module.RequestsScreen,
            ),
          },
          {
            path: "model-health",
            element: lazyScreen(
              () => import("@/components/screens/ModelHealthScreen"),
              (module) => module.ModelHealthScreen,
            ),
          },
          {
            path: "api-keys",
            element: lazyScreen(
              () => import("@/components/screens/ApiKeysScreen"),
              (module) => module.ApiKeysScreen,
            ),
          },
          {
            path: "cronjobs",
            element: lazyScreen(
              () => import("@/components/screens/CronjobsScreen"),
              (module) => module.CronjobsScreen,
            ),
          },
          {
            path: "backups",
            element: lazyScreen(
              () => import("@/components/screens/BackupsScreen"),
              (module) => module.BackupsScreen,
            ),
          },
          {
            path: "settings",
            element: lazyScreen(
              () => import("@/components/settings/SettingsScreen"),
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
