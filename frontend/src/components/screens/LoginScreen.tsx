import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { PublicBranding } from "@/lib/api/app";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import { getLoginAccessToken, setStoredToken } from "@/lib/auth";
import { titleForLocale, useI18n } from "@/lib/I18nContext";

/** Render the administrator login screen. */
export function LoginScreen() {
  const navigate = useNavigate();
  const { locale, t } = useI18n();
  const [branding, setBranding] = useState<PublicBranding | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;

    void apiRequest<PublicBranding>("/public/branding")
      .catch(() => null)
      .then((value) => {
        if (active) setBranding(value);
      });

    return () => {
      active = false;
    };
  }, []);

  const siteName = branding?.site_name?.trim() || "Lens";
  const logoUrl = branding?.logo_url?.trim() || "/logo.svg";
  const loginInputClassName =
    "h-9 rounded-lg border-border/80 bg-pure/70 px-3 shadow-none transition-[color,box-shadow,border-color] focus-visible:border-primary/50 focus-visible:ring-[1px] focus-visible:ring-primary/30 dark:bg-card/70";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);

    try {
      const response = await apiRequest<unknown>("/admin/session", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const accessToken = getLoginAccessToken(response);
      if (!accessToken) throw new Error("Invalid login response");
      setStoredToken(accessToken);
      navigate("/");
    } catch (requestError) {
      toast.error(
        getApiErrorMessage(
          requestError,
          titleForLocale(locale, "登录失败", "Login failed"),
        ),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative flex min-h-svh items-center justify-center bg-background px-4 py-8 text-foreground">
      <div className="w-full max-w-[348px]">
        <img
          src={logoUrl}
          alt=""
          width={44}
          height={44}
          loading="eager"
          fetchPriority="high"
          className="mx-auto size-11 rounded-xl object-contain"
        />
        <h1 className="mt-3 text-center text-base font-semibold tracking-tight text-card-foreground">
          {siteName}
        </h1>

        <form className="mt-5 space-y-4 px-1" onSubmit={submit}>
          <div className="space-y-1.5">
            <label
              className="block text-[13px] font-medium leading-5 text-foreground/85"
              htmlFor="login-username"
            >
              {titleForLocale(locale, "账号", "Account")} *
            </label>
            <Input
              id="login-username"
              name="username"
              autoComplete="username"
              className={loginInputClassName}
              placeholder={t.username}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <label
              className="block text-[13px] font-medium leading-5 text-foreground/85"
              htmlFor="login-password"
            >
              {t.password} *
            </label>
            <Input
              id="login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              className={loginInputClassName}
              placeholder={t.password}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>
          <Button
            type="submit"
            className="mt-2 h-9 w-full rounded-lg text-[13px] shadow-none hover:bg-primary/90"
            disabled={submitting}
          >
            {submitting ? t.signingIn : t.signIn}
          </Button>
        </form>
      </div>

      <a
        href="https://github.com/dyedd/lens"
        target="_blank"
        rel="noreferrer"
        className="absolute bottom-5 text-center font-mono text-xs text-muted-foreground transition-colors hover:text-foreground"
      >
        powered by lens
      </a>
    </main>
  );
}
