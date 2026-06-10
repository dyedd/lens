"use client";

import { Globe2 } from "lucide-react";
import Image from "next/image";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { toast } from "sonner";
import { ApiError, apiRequest, type PublicBranding } from "@/lib/api";
import { setStoredToken } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export function LoginScreen() {
  const router = useRouter();
  const { locale, setLocale, t } = useI18n();
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
  const nextLocale = locale === "zh-CN" ? "en-US" : "zh-CN";
  const languageActionLabel =
    locale === "zh-CN" ? "切换到 English" : "Switch to 中文";
  const loginTitle =
    locale === "zh-CN" ? `欢迎登录 ${siteName}` : `Sign in to ${siteName}`;
  const usernamePlaceholder =
    locale === "zh-CN" ? "请输入用户名" : "Enter username";
  const passwordPlaceholder =
    locale === "zh-CN" ? "请输入密码" : "Enter password";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);

    try {
      const data = await apiRequest<LoginResponse>("/admin/session", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
      });
      setStoredToken(data.access_token);
      router.push("/");
    } catch (requestError) {
      toast.error(
        requestError instanceof ApiError
          ? requestError.message
          : "Login failed",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-svh w-full items-center justify-center bg-background p-6 md:p-10">
      <div className="absolute right-6 top-6 flex items-center gap-2">
        <ThemeToggle />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={languageActionLabel}
              onClick={() => setLocale(nextLocale)}
            >
              <Globe2 />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" align="end">
            {languageActionLabel}
          </TooltipContent>
        </Tooltip>
      </div>

      <main className="flex w-full max-w-sm flex-col items-center">
        <header className="flex flex-col items-center gap-3 text-center">
          <div className="relative size-10 overflow-hidden rounded-lg">
            <Image
              src={logoUrl}
              alt={siteName}
              fill
              loading="eager"
              className="object-contain"
              unoptimized={logoUrl !== "/logo.svg"}
            />
          </div>
          <h1 className="text-xl leading-tight font-semibold text-foreground">
            {loginTitle}
          </h1>
        </header>

        <form onSubmit={submit} className="mt-8 flex w-full flex-col gap-7">
          <FieldGroup className="gap-6">
            <Field className="gap-3">
              <FieldLabel
                htmlFor="login-username"
                className="text-base leading-none font-normal text-foreground"
              >
                {t.username}
              </FieldLabel>
              <Input
                id="login-username"
                name="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder={usernamePlaceholder}
                autoComplete="username"
                required
                autoFocus
                className="rounded-lg border-border bg-background px-4 shadow-xs"
              />
            </Field>

            <Field className="gap-3">
              <FieldLabel
                htmlFor="login-password"
                className="text-base leading-none font-normal text-foreground"
              >
                {t.password}
              </FieldLabel>
              <Input
                id="login-password"
                name="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={passwordPlaceholder}
                autoComplete="current-password"
                required
                className="rounded-lg border-border bg-background px-4 shadow-xs"
              />
            </Field>
          </FieldGroup>

          <Button
            type="submit"
            className="w-full rounded-lg text-base font-normal shadow-xs hover:bg-primary/90 active:bg-primary/90"
            disabled={submitting}
          >
            {submitting ? t.signingIn : t.signIn}
          </Button>
        </form>

        <footer className="mt-6 text-center text-xs text-muted-foreground">
          <a
            href="https://github.com/dyedd/lens"
            target="_blank"
            rel="noreferrer"
            className="font-medium text-foreground hover:underline"
          >
            powered by lens
          </a>
        </footer>
      </main>
    </div>
  );
}
