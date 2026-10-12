import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

type Props = {
  open: boolean;
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onConfirmDiscard: () => void;
};

/** Renders an in-app dialog confirming whether to discard unsaved changes. */
export function UnsavedChangesDialog({
  open,
  locale,
  onOpenChange,
  onConfirmDiscard,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <AppDialogContent
        className="max-w-md"
        showCloseButton={false}
        title={titleForLocale(
          locale,
          "放弃未保存的修改？",
          "Discard unsaved changes?",
        )}
        description={titleForLocale(
          locale,
          "当前表单有未保存的修改。离开后这些修改会丢失。",
          "You have unsaved changes. Leaving now will discard them.",
        )}
        footer={
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
            >
              {titleForLocale(locale, "继续编辑", "Keep editing")}
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={() => {
                onOpenChange(false);
                onConfirmDiscard();
              }}
            >
              {titleForLocale(locale, "放弃修改", "Discard changes")}
            </Button>
          </>
        }
      />
    </Dialog>
  );
}
