import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  type AdminProfile,
  type AdminProfileUpdatePayload,
  type AdminProfileUpdateResponse,
  apiRequest,
  getApiErrorMessage,
} from "@/lib/api";
import { setStoredToken } from "@/lib/auth";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

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
  const { data: profile } = useQuery({
    queryKey: ["auth-me"],
    queryFn: () => apiRequest<AdminProfile>("/admin/session"),
    staleTime: 5 * 60_000,
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

  const setCurrentPassword = useCallback((currentPassword: string) => {
    setAccountForm((current) => ({ ...current, currentPassword }));
  }, []);

  const setNewPassword = useCallback((newPassword: string) => {
    setAccountForm((current) => ({ ...current, newPassword }));
  }, []);

  const setConfirmPassword = useCallback((confirmPassword: string) => {
    setAccountForm((current) => ({ ...current, confirmPassword }));
  }, []);

  const submitAccount = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      const nextUsername = accountForm.username.trim();
      const wantsPasswordUpdate = Boolean(
        accountForm.currentPassword ||
        accountForm.newPassword ||
        accountForm.confirmPassword,
      );
      const usernameChanged = nextUsername !== (profile?.username || "admin");

      if (!nextUsername) {
        toast.error(
          titleForLocale(locale, "用户名不能为空", "Username is required"),
        );
        return;
      }
      if (!usernameChanged && !wantsPasswordUpdate) {
        toast.success(
          titleForLocale(
            locale,
            "没有需要保存的账号变更",
            "No account changes to save",
          ),
        );
        return;
      }
      if (
        wantsPasswordUpdate &&
        (!accountForm.currentPassword || !accountForm.newPassword)
      ) {
        toast.error(
          titleForLocale(
            locale,
            "请填写完整密码",
            "Please fill in both passwords",
          ),
        );
        return;
      }
      if (accountForm.newPassword !== accountForm.confirmPassword) {
        toast.error(
          titleForLocale(
            locale,
            "两次新密码不一致",
            "The new passwords do not match",
          ),
        );
        return;
      }

      const payload: AdminProfileUpdatePayload = {
        username: nextUsername,
        current_password: accountForm.currentPassword,
        new_password: accountForm.newPassword,
      };
      setIsUpdatingAccount(true);
      try {
        const response = await apiRequest<AdminProfileUpdateResponse>(
          "/admin/profile",
          {
            method: "PUT",
            body: JSON.stringify(payload),
          },
        );
        setStoredToken(response.access_token);
        window.sessionStorage.removeItem("lens_admin_profile_cache");
        queryClient.setQueryData(["auth-me"], response.profile);
        await queryClient.invalidateQueries({ queryKey: ["auth-me"] });
        toast.success(titleForLocale(locale, "账号已更新", "Account updated"));
        setAccountForm({
          username: response.profile.username,
          currentPassword: "",
          newPassword: "",
          confirmPassword: "",
        });
      } catch (requestError) {
        const message = getApiErrorMessage(
          requestError,
          titleForLocale(locale, "更新账号失败", "Failed to update account"),
        );
        toast.error(message);
      } finally {
        setIsUpdatingAccount(false);
      }
    },
    [accountForm, locale, profile?.username, queryClient],
  );

  return {
    accountForm,
    isUpdatingAccount,
    setUsername,
    setCurrentPassword,
    setNewPassword,
    setConfirmPassword,
    submitAccount,
  };
}
