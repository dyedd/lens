import { skipToken, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import {
  ADMIN_PASSWORD_MIN_LENGTH,
  ADMIN_PROFILE_QUERY_KEY,
  type AdminProfile,
  type AdminProfileUpdatePayload,
} from "@/lib/api/app";
import {
  ApiError,
  apiRequest,
  getApiErrorMessage,
  isRecord,
} from "@/lib/api/client";
import {
  getLoginAccessToken,
  getStoredToken,
  isAdminProfile,
  setStoredToken,
} from "@/lib/auth";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

interface AccountForm {
  username: string;
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

const EMPTY_ACCOUNT_FORM: AccountForm = {
  username: "admin",
  currentPassword: "",
  newPassword: "",
  confirmPassword: "",
};

/** Manage the administrator profile form and update request. */
export function useAccountSettings(locale: Locale) {
  const queryClient = useQueryClient();
  const { data: profile } = useQuery<AdminProfile>({
    queryKey: ADMIN_PROFILE_QUERY_KEY,
    queryFn: skipToken,
  });
  const [accountForm, setAccountForm] =
    useState<AccountForm>(EMPTY_ACCOUNT_FORM);
  const [isUpdatingAccount, setIsUpdatingAccount] = useState(false);

  useEffect(() => {
    setAccountForm((current) => ({
      ...current,
      username: profile?.username || "admin",
    }));
  }, [profile?.username]);

  const setUsername = useCallback((username: string) => {
    setAccountForm((current) => ({ ...current, username }));
  }, []);

  const setNewPassword = useCallback((newPassword: string) => {
    setAccountForm((current) => ({ ...current, newPassword }));
  }, []);

  const setConfirmPassword = useCallback((confirmPassword: string) => {
    setAccountForm((current) => ({ ...current, confirmPassword }));
  }, []);

  const submitAccount = useCallback(
    async (currentPassword: string) => {
      if (!profile) return false;
      const nextUsername = accountForm.username.trim();
      const wantsPasswordUpdate = Boolean(
        accountForm.newPassword || accountForm.confirmPassword,
      );
      const usernameChanged = nextUsername !== profile.username;

      if (!nextUsername) {
        toast.error(
          titleForLocale(locale, "用户名不能为空", "Username is required"),
        );
        return false;
      }
      if (!usernameChanged && !wantsPasswordUpdate) {
        toast.success(
          titleForLocale(
            locale,
            "没有需要保存的账号变更",
            "No account changes to save",
          ),
        );
        return false;
      }
      if (
        wantsPasswordUpdate &&
        (!currentPassword || !accountForm.newPassword)
      ) {
        toast.error(
          titleForLocale(
            locale,
            "请填写完整密码",
            "Please fill in both passwords",
          ),
        );
        return false;
      }
      if (accountForm.newPassword !== accountForm.confirmPassword) {
        toast.error(
          titleForLocale(
            locale,
            "两次新密码不一致",
            "The new passwords do not match",
          ),
        );
        return false;
      }
      if (
        wantsPasswordUpdate &&
        (Array.from(accountForm.newPassword).length <
          ADMIN_PASSWORD_MIN_LENGTH ||
          !accountForm.newPassword.trim())
      ) {
        toast.error(
          titleForLocale(
            locale,
            `新密码至少需要 ${ADMIN_PASSWORD_MIN_LENGTH} 个字符`,
            `The new password must contain at least ${ADMIN_PASSWORD_MIN_LENGTH} characters`,
          ),
        );
        return false;
      }

      const payload: AdminProfileUpdatePayload = {
        username: nextUsername,
        current_password: currentPassword,
        new_password: accountForm.newPassword,
      };
      setIsUpdatingAccount(true);
      try {
        const token = getStoredToken();
        const response = await apiRequest<unknown>("/admin/profile", {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        if (!token || getStoredToken() !== token) return false;
        if (!isRecord(response)) {
          throw new ApiError("Invalid admin profile response from API", 200);
        }
        const accessToken = getLoginAccessToken(response);
        const updatedProfile = response.profile;
        if (
          !accessToken ||
          !isAdminProfile(updatedProfile) ||
          updatedProfile.id !== profile.id
        ) {
          throw new ApiError("Invalid admin profile response from API", 200);
        }
        setStoredToken(accessToken, updatedProfile.id);
        queryClient.setQueryData(ADMIN_PROFILE_QUERY_KEY, updatedProfile);
        toast.success(titleForLocale(locale, "账号已更新", "Account updated"));
        setAccountForm({
          username: updatedProfile.username,
          currentPassword: "",
          newPassword: "",
          confirmPassword: "",
        });
        return true;
      } catch (requestError) {
        const message = getApiErrorMessage(
          requestError,
          titleForLocale(locale, "更新账号失败", "Failed to update account"),
        );
        toast.error(message);
        return false;
      } finally {
        setIsUpdatingAccount(false);
      }
    },
    [accountForm, locale, profile, queryClient],
  );

  return {
    accountForm,
    isUpdatingAccount,
    setUsername,
    setNewPassword,
    setConfirmPassword,
    submitAccount,
  };
}
