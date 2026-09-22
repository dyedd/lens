import type { ComponentProps, ReactNode } from "react";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/Field";
import { Separator } from "@/components/ui/Separator";
import { cn } from "@/lib/classNames";

export function SettingsPage({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "space-y-6 pb-8 md:space-y-7 xl:space-y-8 xl:pb-10",
        className,
      )}
      {...props}
    />
  );
}

export function SettingsSection({
  title,
  actions,
  children,
  className,
  headerClassName,
  ...props
}: Omit<ComponentProps<"section">, "title"> & {
  title?: ReactNode;
  actions?: ReactNode;
  headerClassName?: string;
}) {
  return (
    <section
      className={cn("space-y-4 px-0.5 md:space-y-5 xl:space-y-6", className)}
      {...props}
    >
      {title || actions ? (
        <div
          className={cn(
            actions
              ? "flex h-9 items-center justify-between gap-2 md:h-10 md:gap-3"
              : "flex h-9 items-center md:h-10",
            headerClassName,
          )}
        >
          <div className="min-w-0">
            {title ? <h3 className="text-sm font-semibold">{title}</h3> : null}
          </div>
          {actions ? (
            <div className="flex shrink-0 items-center justify-end gap-2">
              {actions}
            </div>
          ) : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function SettingsFieldRow({
  title,
  description,
  htmlFor,
  children,
  className,
  controlClassName,
  invalid = false,
}: {
  title: ReactNode;
  description?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
  className?: string;
  controlClassName?: string;
  invalid?: boolean;
}) {
  return (
    <Field data-invalid={invalid} className={className}>
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:gap-4 xl:gap-6">
        <div className="min-w-0 flex-1">
          <FieldLabel htmlFor={htmlFor}>{title}</FieldLabel>
          {description ? (
            <FieldDescription className="text-[11px]">
              {description}
            </FieldDescription>
          ) : null}
        </div>
        <div
          className={cn(
            "flex w-full min-w-0 flex-col justify-start gap-1 md:w-44 md:shrink-0 md:items-end xl:w-52",
            controlClassName,
          )}
        >
          {children}
        </div>
      </div>
    </Field>
  );
}

export function SettingsFieldList({
  className,
  ...props
}: ComponentProps<typeof FieldGroup>) {
  return <FieldGroup className={cn("gap-3 md:gap-4", className)} {...props} />;
}

export function SettingsSectionSeparator({
  className,
  ...props
}: ComponentProps<typeof Separator>) {
  return (
    <Separator
      className={cn("mx-0.5 my-7 md:my-8 xl:mx-1 xl:my-10", className)}
      {...props}
    />
  );
}
