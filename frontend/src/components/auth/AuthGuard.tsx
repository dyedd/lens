import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/Button";
import { AppLoadingScreen } from "@/components/ui/LoadingState";
import type { AdminProfile } from "@/lib/api/app";
import { apiRequest } from "@/lib/api/client";
import {
  getStoredToken,
  SESSION_CACHE_KEY,
  shouldRedirectAfterSessionCheckFailure,
  signOut,
} from "@/lib/auth";
import { titleForLocale, useI18n } from "@/lib/I18nContext";

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
  const { locale } = useI18n();
  const [status, setStatus] = useState<"checking" | "ready" | "failed">(
    "checking",
  );

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

      if (readCachedProfile()) {
        setStatus("ready");
        return;
      }

      try {
        const profile = await apiRequest<AdminProfile>("/admin/session");
        if (!cancelled) {
          writeCachedProfile(profile);
          setStatus("ready");
        }
      } catch {
        if (cancelled) {
          return;
        }
        if (shouldRedirectAfterSessionCheckFailure(getStoredToken())) {
          navigate("/login", { replace: true });
        } else {
          setStatus("failed");
        }
      }
    }

    if (status === "checking") void verify();
    window.addEventListener("storage", handleStorage);

    return () => {
      cancelled = true;
      window.removeEventListener("storage", handleStorage);
    };
  }, [navigate, status]);

  if (status === "failed") {
    return (
      <main className="flex min-h-dvh flex-col items-center justify-center gap-3 bg-background p-4 text-center">
        <p role="alert" className="text-sm text-destructive">
          {titleForLocale(
            locale,
            "无法验证登录状态",
            "Could not verify session",
          )}
        </p>
        <Button type="button" onClick={() => setStatus("checking")}>
          {titleForLocale(locale, "重试", "Retry")}
        </Button>
      </main>
    );
  }

  return status === "ready" ? children : <AppLoadingScreen />;
}
