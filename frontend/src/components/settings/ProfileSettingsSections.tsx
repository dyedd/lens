import { AccountSettings } from "@/components/settings/AccountSettings";
import { AppearanceSettings } from "@/components/settings/AppearanceSettings";
import { TabsContent } from "@/components/ui/Tabs";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import { SettingsSectionCard } from "./SettingsSectionCard";
import type { useAccountSettings } from "./useAccountSettings";
import type { useSettingsDraft } from "./useSettingsDraft";

type AccountSettingsController = ReturnType<typeof useAccountSettings>;
type SettingsDraftController = ReturnType<typeof useSettingsDraft>;

interface SettingsSectionProps {
  locale: Locale;
  settings: SettingsDraftController;
}

/** Render the appearance settings tab content. */
export function GeneralSettingsSection({
  locale,
  settings,
  account,
}: SettingsSectionProps & { account: AccountSettingsController }) {
  return (
    <TabsContent value="general" className="mt-0 space-y-8">
      <SettingsSectionCard title={titleForLocale(locale, "外观", "Appearance")}>
        <AppearanceSettings
          siteName={settings.draft.siteName}
          siteLogoUrl={settings.draft.siteLogoUrl}
          onSiteNameChange={(value) =>
            settings.setDraftValue("siteName", value)
          }
          onSiteLogoUrlChange={(value) =>
            settings.setDraftValue("siteLogoUrl", value)
          }
          timeZone={settings.draft.timeZone}
          onTimeZoneChange={(value) =>
            settings.setDraftValue("timeZone", value)
          }
        />
      </SettingsSectionCard>
      <AccountSettingsSection locale={locale} account={account} />
    </TabsContent>
  );
}

/** Render the administrator account settings tab content. */
export function AccountSettingsSection({
  account,
  locale,
  embedded = false,
}: {
  account: AccountSettingsController;
  locale: Locale;
  embedded?: boolean;
}) {
  const content = (
    <AccountSettings
      username={account.accountForm.username}
      newPassword={account.accountForm.newPassword}
      confirmPassword={account.accountForm.confirmPassword}
      updatingAccount={account.isUpdatingAccount}
      onUsernameChange={account.setUsername}
      onNewPasswordChange={account.setNewPassword}
      onConfirmPasswordChange={account.setConfirmPassword}
      onSubmit={account.submitAccount}
    />
  );
  return embedded ? (
    <div className="mt-3">{content}</div>
  ) : (
    <SettingsSectionCard
      title={titleForLocale(locale, "管理员账号", "Admin account")}
    >
      {content}
    </SettingsSectionCard>
  );
}
