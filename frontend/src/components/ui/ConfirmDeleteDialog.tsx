import type { ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

type Props = {
  open: boolean;
  locale: Locale;
  title: string;
  description: ReactNode;
  isBusy?: boolean;
  isDisabled?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  children?: ReactNode;
};

/** Renders the shared destructive confirmation dialog. */
export function ConfirmDeleteDialog({
  open,
  locale,
  title,
  description,
  isBusy = false,
  isDisabled = false,
  onOpenChange,
  onConfirm,
  children,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <AppDialogContent
        className="max-w-lg"
        showCloseButton={false}
        title={title}
        description={description}
        footer={
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isBusy}
              onClick={() => onOpenChange(false)}
            >
              {titleForLocale(locale, "取消", "Cancel")}
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              disabled={isBusy || isDisabled}
              onClick={onConfirm}
            >
              {isBusy
                ? titleForLocale(locale, "删除中...", "Deleting...")
                : titleForLocale(locale, "确认删除", "Delete")}
            </Button>
          </>
        }
      >
        {children}
      </AppDialogContent>
    </Dialog>
  );
}
