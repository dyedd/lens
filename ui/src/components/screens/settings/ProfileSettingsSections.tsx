import { AccountSettings } from "@/components/settings/AccountSettings";
import { AppearanceSettings } from "@/components/settings/AppearanceSettings";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { TabsContent } from "@/components/ui/Tabs";
import { Textarea } from "@/components/ui/Textarea";
import { titleForLocale, type Locale } from "@/lib/I18nContext";
import { DEFAULT_MODEL_TEST_PROMPTS } from "@/lib/modelTestPrompts";

import { TIME_ZONE_OPTIONS } from "./settingsDraft";
import { SettingsSectionCard } from "./SettingsSectionCard";
import { type useAccountSettings } from "./useAccountSettings";
import { type useSettingsDraft } from "./useSettingsDraft";

type AccountSettingsController = ReturnType<typeof useAccountSettings>;
type SettingsDraftController = ReturnType<typeof useSettingsDraft>;

interface SettingsSectionProps {
  description: string;
  locale: Locale;
  settings: SettingsDraftController;
}

/** Render the appearance settings tab content. */
export function AppearanceSettingsSection({
  description,
  locale,
  settings,
}: SettingsSectionProps) {
  return (
    <TabsContent value="appearance" className="mt-0">
      <SettingsSectionCard
        title={titleForLocale(locale, "站点外观", "Appearance")}
        description={description}
      >
        <AppearanceSettings
          siteName={settings.draft.siteName}
          siteLogoUrl={settings.draft.siteLogoUrl}
          onSiteNameChange={(value) =>
            settings.setDraftValue("siteName", value)
          }
          onSiteLogoUrlChange={(value) =>
            settings.setDraftValue("siteLogoUrl", value)
          }
        />
      </SettingsSectionCard>
    </TabsContent>
  );
}

/** Render the administrator account settings tab content. */
export function AccountSettingsSection({
  account,
  description,
  locale,
}: {
  account: AccountSettingsController;
  description: string;
  locale: Locale;
}) {
  return (
    <TabsContent value="account" className="mt-0">
      <SettingsSectionCard
        title={titleForLocale(locale, "账号", "Account")}
        description={description}
      >
        <AccountSettings
          username={account.accountForm.username}
          currentPassword={account.accountForm.currentPassword}
          newPassword={account.accountForm.newPassword}
          confirmPassword={account.accountForm.confirmPassword}
          updatingAccount={account.isUpdatingAccount}
          onUsernameChange={account.setUsername}
          onCurrentPasswordChange={account.setCurrentPassword}
          onNewPasswordChange={account.setNewPassword}
          onConfirmPasswordChange={account.setConfirmPassword}
          onSubmit={account.submitAccount}
        />
      </SettingsSectionCard>
    </TabsContent>
  );
}

/** Render the display time zone settings tab content. */
export function TimeSettingsSection({
  description,
  locale,
  settings,
}: SettingsSectionProps) {
  return (
    <TabsContent value="time" className="mt-0">
      <SettingsSectionCard
        title={titleForLocale(locale, "时间", "Time")}
        description={description}
      >
        <FieldGroup>
          <Field>
            <FieldLabel>
              {titleForLocale(locale, "时区", "Time zone")}
            </FieldLabel>
            <Combobox
              className="w-full"
              value={settings.draft.timeZone || "Asia/Shanghai"}
              onChange={(event) =>
                settings.setDraftValue("timeZone", event.target.value)
              }
            >
              {TIME_ZONE_OPTIONS.map((option) => (
                <ComboboxOption key={option.value} value={option.value}>
                  {option.label}
                </ComboboxOption>
              ))}
            </Combobox>
          </Field>
        </FieldGroup>
      </SettingsSectionCard>
    </TabsContent>
  );
}

/** Render the model test prompt settings tab content. */
export function ModelTestSettingsSection({
  description,
  locale,
  settings,
}: SettingsSectionProps) {
  return (
    <TabsContent value="model-test" className="mt-0">
      <SettingsSectionCard
        title={titleForLocale(locale, "模型测试", "Model test")}
        description={description}
      >
        <FieldGroup>
          <Field>
            <FieldLabel>
              {titleForLocale(locale, "预设问题", "Preset prompts")}
            </FieldLabel>
            <Textarea
              className="min-h-[132px]"
              value={settings.draft.modelTestPrompts}
              onChange={(event) =>
                settings.setDraftValue("modelTestPrompts", event.target.value)
              }
              placeholder={DEFAULT_MODEL_TEST_PROMPTS.join("\n")}
            />
          </Field>
        </FieldGroup>
      </SettingsSectionCard>
    </TabsContent>
  );
}
