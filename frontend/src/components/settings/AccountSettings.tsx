import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { titleForLocale, useI18n } from "@/lib/I18nContext";
import { SettingsFieldList, SettingsFieldRow } from "./settingsLayout";

interface AccountSettingsProps {
  username: string;
  newPassword: string;
  confirmPassword: string;
  updatingAccount: boolean;
  onUsernameChange: (value: string) => void;
  onNewPasswordChange: (value: string) => void;
  onConfirmPasswordChange: (value: string) => void;
  onSubmit: (currentPassword: string) => Promise<boolean>;
}

/** Renders the administrator account update form. */
export function AccountSettings({
  username,
  newPassword,
  confirmPassword,
  updatingAccount,
  onUsernameChange,
  onNewPasswordChange,
  onConfirmPasswordChange,
  onSubmit,
}: AccountSettingsProps) {
  const { locale } = useI18n();
  const [isPasswordDialogOpen, setIsPasswordDialogOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const hasPasswordChange = Boolean(newPassword);
  const savedUsername = useRef(username);

  useEffect(() => {
    savedUsername.current = username;
  }, [username]);

  async function confirmUpdate() {
    if (await onSubmit(currentPassword)) {
      setIsPasswordDialogOpen(false);
      setCurrentPassword("");
    }
  }

  return (
    <>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          setIsPasswordDialogOpen(true);
        }}
      >
        <SettingsFieldList>
          <SettingsFieldRow
            title={titleForLocale(locale, "用户名", "Username")}
          >
            <Input
              className="w-full"
              required
              value={username}
              onChange={(event) => onUsernameChange(event.target.value)}
              onBlur={() => {
                if (username.trim() !== savedUsername.current.trim()) {
                  setIsPasswordDialogOpen(true);
                }
              }}
              autoComplete="username"
            />
          </SettingsFieldRow>
          <SettingsFieldRow
            title={titleForLocale(locale, "新密码", "New password")}
          >
            <Input
              className="w-full"
              type="password"
              value={newPassword}
              onChange={(event) => onNewPasswordChange(event.target.value)}
              autoComplete="new-password"
            />
          </SettingsFieldRow>
          {hasPasswordChange ? (
            <SettingsFieldRow
              title={titleForLocale(
                locale,
                "确认新密码",
                "Confirm new password",
              )}
            >
              <Input
                className="w-full"
                type="password"
                value={confirmPassword}
                onChange={(event) =>
                  onConfirmPasswordChange(event.target.value)
                }
                onBlur={() => {
                  if (confirmPassword) setIsPasswordDialogOpen(true);
                }}
                autoComplete="new-password"
              />
            </SettingsFieldRow>
          ) : null}
        </SettingsFieldList>
      </form>
      <Dialog
        open={isPasswordDialogOpen}
        onOpenChange={setIsPasswordDialogOpen}
      >
        <AppDialogContent
          showCloseButton={false}
          title={titleForLocale(
            locale,
            "验证当前密码",
            "Verify current password",
          )}
          description={titleForLocale(
            locale,
            "请输入当前密码以确认本次账号修改。",
            "Enter your current password to confirm this account change.",
          )}
          footer={
            <>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setIsPasswordDialogOpen(false)}
              >
                {titleForLocale(locale, "取消", "Cancel")}
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={updatingAccount || !currentPassword}
                onClick={() => void confirmUpdate()}
              >
                {updatingAccount
                  ? titleForLocale(locale, "提交中...", "Updating...")
                  : titleForLocale(locale, "确认", "Confirm")}
              </Button>
            </>
          }
        >
          <Input
            type="password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            autoComplete="current-password"
            autoFocus
          />
        </AppDialogContent>
      </Dialog>
    </>
  );
}
