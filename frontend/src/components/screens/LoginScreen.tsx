import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { PublicBranding } from "@/lib/api/app";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import { setStoredToken } from "@/lib/auth";
import { titleForLocale, useI18n } from "@/lib/I18nContext";

type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

/** Render the administrator login screen. */
export function LoginScreen() {
  const navigate = useNavigate();
  const { locale, t } = useI18n();
  const { data: branding } = useQuery({
    queryKey: ["public-branding"],
    queryFn: () => apiRequest<PublicBranding>("/public/branding"),
    staleTime: 5 * 60_000,
  });
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const siteName = branding?.site_name?.trim() || "Lens";
  const logoUrl = branding?.logo_url?.trim() || "/logo.svg";
  const loginInputClassName =
    "h-9 rounded-md border-input/40 px-3 shadow-none transition-[color,box-shadow] focus-visible:border-primary/60 focus-visible:ring-[1px] focus-visible:ring-primary/40";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);

    try {
      const data = await apiRequest<LoginResponse>("/admin/session", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
      });
      setStoredToken(data.access_token);
      navigate("/");
    } catch (requestError) {
      toast.error(getApiErrorMessage(requestError, "Login failed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative flex min-h-svh items-center justify-center bg-background px-4 py-8 text-foreground">
      <div className="w-full max-w-[360px]">
        <img
          src={logoUrl}
          alt={siteName}
          width={32}
          height={32}
          loading="eager"
          className="mx-auto h-12 w-auto object-contain"
        />

        <form className="mt-7 space-y-4 px-2" onSubmit={submit}>
          <div className="space-y-2">
            <label
              className="text-sm font-medium leading-none text-foreground"
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
          <div className="space-y-2">
            <label
              className="text-sm font-medium leading-none text-foreground"
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
            className="mt-2 h-9 w-full rounded-md text-sm font-semibold shadow-none hover:bg-primary/90"
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
        className="absolute bottom-4 text-center text-xs font-medium text-muted-foreground hover:text-foreground hover:underline"
      >
        powered by lens
      </a>
    </main>
  );
}
