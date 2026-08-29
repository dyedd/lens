import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { AppLoadingScreen } from "@/components/ui/LoadingState";
import type { AdminProfile } from "@/lib/api/app";
import { ApiError, apiRequest } from "@/lib/api/client";
import { clearStoredToken, getStoredToken } from "@/lib/auth";

const SESSION_CACHE_KEY = "lens_admin_profile_cache";
const SESSION_CACHE_TTL_MS = 60_000;
const SESSION_CACHE_VERSION = 1;

function withSessionStorageFallback<T>(action: () => T, fallback: T): T {
  try {
    return action();
  } catch {
    return fallback;
  }
}

/** Verifies the admin session before rendering protected content. */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const [state, setState] = useState<{
    ready: boolean;
    profile: AdminProfile | null;
  }>({ ready: false, profile: null });

  useEffect(() => {
    let cancelled = false;

    function readCachedProfile() {
      return withSessionStorageFallback<AdminProfile | null>(() => {
        const raw = window.sessionStorage.getItem(SESSION_CACHE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw) as {
          version: number;
          profile: AdminProfile;
          expiresAt: number;
        };
        if (
          parsed.version !== SESSION_CACHE_VERSION ||
          parsed.expiresAt < Date.now()
        ) {
          window.sessionStorage.removeItem(SESSION_CACHE_KEY);
          return null;
        }
        return parsed.profile;
      }, null);
    }

    function writeCachedProfile(profile: AdminProfile) {
      withSessionStorageFallback(
        () =>
          window.sessionStorage.setItem(
            SESSION_CACHE_KEY,
            JSON.stringify({
              version: SESSION_CACHE_VERSION,
              profile,
              expiresAt: Date.now() + SESSION_CACHE_TTL_MS,
            }),
          ),
        undefined,
      );
    }

    function clearCachedProfile() {
      withSessionStorageFallback(
        () => window.sessionStorage.removeItem(SESSION_CACHE_KEY),
        undefined,
      );
    }

    async function verify() {
      if (!getStoredToken()) {
        navigate("/login", { replace: true });
        return;
      }

      const cachedProfile = readCachedProfile();
      if (cachedProfile) {
        setState({ ready: true, profile: cachedProfile });
        return;
      }

      try {
        const profile = await apiRequest<AdminProfile>("/admin/session");
        if (!cancelled) {
          writeCachedProfile(profile);
          setState({ ready: true, profile });
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (error instanceof ApiError && error.status === 401) {
          clearStoredToken();
          clearCachedProfile();
        }
        navigate("/login", { replace: true });
      }
    }

    void verify();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  if (!state.ready) {
    return <AppLoadingScreen />;
  }

  return <>{children}</>;
}
