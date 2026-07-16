import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { type SettingItem, apiRequest, getApiErrorMessage } from "@/lib/api";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import {
  createEmptySettingsDraft,
  createSettingItems,
  createSettingsDraft,
} from "./settingsDraft";
import {
  validateNumericSettings,
  type NumericSettingErrors,
} from "./numericSettingsValidation";
import { validateUpstreamHeadersConfig } from "./upstreamHeaderConfig";
import { validateUpstreamParamOverrideConfig } from "./upstreamParamOverride";
import { useSettingsDraftActions } from "./useSettingsDraftActions";

const REFRESH_QUERY_KEYS = [
  ["settings"],
  ["public-branding"],
  ["app-info"],
  ["model-groups"],
  ["overview-summary"],
  ["overview-daily"],
  ["overview-models"],
] as const;

/** Manage loading, editing, refreshing, and saving application settings. */
export function useSettingsDraft(locale: Locale) {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<SettingItem[]>("/admin/settings"),
    staleTime: 5 * 60_000,
  });
  const [draft, setDraft] = useState(createEmptySettingsDraft);
  const [isSaving, setIsSaving] = useState(false);
  const [isNumericValidationVisible, setIsNumericValidationVisible] =
    useState(false);
  const actions = useSettingsDraftActions(setDraft);
  const numericSettingErrors: NumericSettingErrors = isNumericValidationVisible
    ? validateNumericSettings(draft, locale)
    : {};

  useEffect(() => {
    if (settingsQuery.isSuccess) {
      setDraft(createSettingsDraft(settingsQuery.data));
      setIsNumericValidationVisible(false);
    }
  }, [settingsQuery.data, settingsQuery.isSuccess]);

  useEffect(() => {
    if (!settingsQuery.isError) {
      return;
    }
    toast.error(
      titleForLocale(locale, "设置加载失败", "Failed to load settings"),
      {
        id: "settings-load-error",
        description:
          settingsQuery.error instanceof Error
            ? settingsQuery.error.message
            : titleForLocale(
                locale,
                "无法读取系统设置",
                "Unable to read system settings",
              ),
      },
    );
  }, [locale, settingsQuery.error, settingsQuery.isError]);

  const refresh = useCallback(async () => {
    await Promise.all(
      REFRESH_QUERY_KEYS.map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    );
  }, [queryClient]);

  const submitSettings = useCallback(async () => {
    if (!settingsQuery.isSuccess) {
      return;
    }
    const numericErrors = validateNumericSettings(draft, locale);
    setIsNumericValidationVisible(true);
    const numericError = Object.values(numericErrors).find(Boolean);
    if (numericError) {
      toast.error(numericError);
      return;
    }
    const upstreamHeadersError = validateUpstreamHeadersConfig(
      draft.upstreamHeadersConfig,
      locale,
    );
    if (upstreamHeadersError) {
      toast.error(upstreamHeadersError);
      return;
    }
    const upstreamParamOverrideError = validateUpstreamParamOverrideConfig(
      draft.upstreamParamOverrideConfig,
      locale,
    );
    if (upstreamParamOverrideError) {
      toast.error(upstreamParamOverrideError);
      return;
    }

    setIsSaving(true);
    try {
      await apiRequest<SettingItem[]>("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({ items: createSettingItems(draft) }),
      });
      toast.success(titleForLocale(locale, "设置已保存", "Settings saved"));
      await refresh();
    } catch (requestError) {
      const message = getApiErrorMessage(
        requestError,
        titleForLocale(locale, "保存设置失败", "Failed to save settings"),
      );
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  }, [draft, locale, refresh, settingsQuery.isSuccess]);

  return {
    draft,
    numericSettingErrors,
    isSaving,
    isSettingsReady: settingsQuery.isSuccess,
    refresh,
    submitSettings,
    ...actions,
  };
}
