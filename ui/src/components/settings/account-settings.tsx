"use client";

import { type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { titleForLocale, useI18n } from "@/lib/i18n";

interface AccountSettingsProps {
  username: string;
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
  updatingAccount: boolean;
  onUsernameChange: (value: string) => void;
  onCurrentPasswordChange: (value: string) => void;
  onNewPasswordChange: (value: string) => void;
  onConfirmPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function AccountSettings({
  username,
  currentPassword,
  newPassword,
  confirmPassword,
  updatingAccount,
  onUsernameChange,
  onCurrentPasswordChange,
  onNewPasswordChange,
  onConfirmPasswordChange,
  onSubmit,
}: AccountSettingsProps) {
  const { locale } = useI18n();

  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit}>
      <FieldGroup>
        <Field>
          <FieldLabel>
            {titleForLocale(locale, "用户名", "Username")}
          </FieldLabel>
          <Input
            value={username}
            onChange={(event) => onUsernameChange(event.target.value)}
            autoComplete="username"
          />
        </Field>
        <Field>
          <FieldLabel>
            {titleForLocale(locale, "当前密码", "Current password")}
          </FieldLabel>
          <Input
            type="password"
            value={currentPassword}
            onChange={(event) => onCurrentPasswordChange(event.target.value)}
            autoComplete="current-password"
          />
        </Field>
        <Field>
          <FieldLabel>
            {titleForLocale(locale, "新密码", "New password")}
          </FieldLabel>
          <Input
            type="password"
            value={newPassword}
            onChange={(event) => onNewPasswordChange(event.target.value)}
            autoComplete="new-password"
          />
        </Field>
        <Field>
          <FieldLabel>
            {titleForLocale(locale, "确认新密码", "Confirm new password")}
          </FieldLabel>
          <Input
            type="password"
            value={confirmPassword}
            onChange={(event) => onConfirmPasswordChange(event.target.value)}
            autoComplete="new-password"
          />
        </Field>
      </FieldGroup>
      <Button type="submit" variant="outline" disabled={updatingAccount}>
        {updatingAccount
          ? titleForLocale(locale, "提交中...", "Updating...")
          : titleForLocale(locale, "保存账号", "Save account")}
      </Button>
    </form>
  );
}
