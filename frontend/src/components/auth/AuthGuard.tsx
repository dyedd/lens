import { Fragment, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/Button";
import { AppLoadingScreen } from "@/components/ui/LoadingState";
import type { AdminProfile } from "@/lib/api/app";
import { apiRequest } from "@/lib/api/client";
import {
  ADMIN_TOKEN_KEY,
  AUTH_CHANGE_EVENT,
  getStoredToken,
  isAdminProfile,
} from "@/lib/auth";
import { titleForLocale, useI18n } from "@/lib/I18nContext";

export function AuthGuard({
  children,
}: {
  children: (profile: AdminProfile) => React.ReactNode;
}) {
  const navigate = useNavigate();
  const { locale } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [verification, setVerification] = useState<{
    attempt: number;
    profile: AdminProfile | null;
  }>();

  useEffect(() => {
    const controller = new AbortController();
    let token = getStoredToken();
    let adminId: number | undefined;

    function verifyNewToken() {
      if (controller.signal.aborted || getStoredToken() === token) return;
      controller.abort();
      setAttempt((current) => current + 1);
    }

    function handleStorage(event: StorageEvent) {
      if (
        event.storageArea === window.localStorage &&
        (event.key === ADMIN_TOKEN_KEY || event.key === null)
      ) {
        verifyNewToken();
      }
    }

    function handleAuthChange(event: Event) {
      const currentToken = getStoredToken();
      if (
        !controller.signal.aborted &&
        currentToken &&
        adminId !== undefined &&
        event instanceof CustomEvent &&
        event.detail === adminId
      ) {
        token = currentToken;
        return;
      }
      verifyNewToken();
    }

    async function verify() {
      if (controller.signal.aborted) return;
      if (!token) {
        navigate("/login", { replace: true });
        return;
      }

      try {
        const profile = await apiRequest<unknown>("/admin/session", {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (getStoredToken() !== token) {
          verifyNewToken();
          return;
        }
        const verifiedProfile = isAdminProfile(profile) ? profile : null;
        adminId = verifiedProfile?.id;
        setVerification({ attempt, profile: verifiedProfile });
      } catch {
        if (controller.signal.aborted) return;
        const currentToken = getStoredToken();
        if (!currentToken) {
          navigate("/login", { replace: true });
        } else if (currentToken !== token) {
          verifyNewToken();
        } else {
          setVerification({ attempt, profile: null });
        }
      }
    }

    window.addEventListener("storage", handleStorage);
    window.addEventListener(AUTH_CHANGE_EVENT, handleAuthChange);
    verifyNewToken();
    void verify();

    return () => {
      controller.abort();
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(AUTH_CHANGE_EVENT, handleAuthChange);
    };
  }, [attempt, navigate]);

  if (verification?.attempt !== attempt) return <AppLoadingScreen />;

  if (!verification.profile) {
    return (
      <main className="flex min-h-dvh flex-col items-center justify-center gap-3 bg-background p-4 text-center">
        <p role="alert" className="text-sm text-destructive">
          {titleForLocale(
            locale,
            "无法验证登录状态",
            "Could not verify session",
          )}
        </p>
        <Button
          type="button"
          onClick={() => setAttempt((current) => current + 1)}
        >
          {titleForLocale(locale, "重试", "Retry")}
        </Button>
      </main>
    );
  }

  return <Fragment key={attempt}>{children(verification.profile)}</Fragment>;
}
