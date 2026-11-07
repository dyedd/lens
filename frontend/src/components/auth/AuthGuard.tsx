import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { AppLoadingScreen } from "@/components/ui/LoadingState";
import type { AdminProfile } from "@/lib/api/app";
import { apiRequest } from "@/lib/api/client";
import { getStoredToken, SESSION_CACHE_KEY, signOut } from "@/lib/auth";

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

    function handleStorage(event: StorageEvent) {
      if (
        event.storageArea === window.localStorage &&
        (event.key === "lens_token" || event.key === null) &&
        !getStoredToken()
      ) {
        signOut();
      }
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
      } catch {
        if (cancelled) {
          return;
        }
        navigate("/login", { replace: true });
      }
    }

    void verify();
    window.addEventListener("storage", handleStorage);

    return () => {
      cancelled = true;
      window.removeEventListener("storage", handleStorage);
    };
  }, [navigate]);

  if (!state.ready) {
    return <AppLoadingScreen />;
  }

  return <>{children}</>;
}
