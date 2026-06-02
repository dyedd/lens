"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, AdminProfile, apiRequest } from "@/lib/api";
import { clearStoredToken, getStoredToken } from "@/lib/auth";
import { AppLoadingScreen } from "@/components/ui/loading-state";

const SESSION_CACHE_KEY = "lens_admin_profile_cache";
const SESSION_CACHE_TTL_MS = 60_000;
const SESSION_CACHE_VERSION = 1;

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<{
    ready: boolean;
    profile: AdminProfile | null;
  }>({ ready: false, profile: null });

  useEffect(() => {
    let cancelled = false;

    function readCachedProfile() {
      const raw = window.sessionStorage.getItem(SESSION_CACHE_KEY);
      if (!raw) return null;
      try {
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
      } catch (error) {
        if (!(error instanceof SyntaxError)) throw error;
        window.sessionStorage.removeItem(SESSION_CACHE_KEY);
        return null;
      }
    }

    function writeCachedProfile(profile: AdminProfile) {
      window.sessionStorage.setItem(
        SESSION_CACHE_KEY,
        JSON.stringify({
          version: SESSION_CACHE_VERSION,
          profile,
          expiresAt: Date.now() + SESSION_CACHE_TTL_MS,
        }),
      );
    }

    async function verify() {
      if (!getStoredToken()) {
        router.replace("/login");
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
          window.sessionStorage.removeItem(SESSION_CACHE_KEY);
        }
        router.replace("/login");
      }
    }

    void verify();

    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!state.ready) {
    return <AppLoadingScreen />;
  }

  return <>{children}</>;
}
