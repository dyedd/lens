"use client";

import Image from "next/image";
import { ImageIcon } from "lucide-react";

import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { titleForLocale, useI18n } from "@/lib/i18n";

interface AppearanceSettingsProps {
  siteName: string;
  siteLogoUrl: string;
  onSiteNameChange: (value: string) => void;
  onSiteLogoUrlChange: (value: string) => void;
}

export function AppearanceSettings({
  siteName,
  siteLogoUrl,
  onSiteNameChange,
  onSiteLogoUrlChange,
}: AppearanceSettingsProps) {
  const { locale, setLocale } = useI18n();

  return (
    <>
      <FieldGroup>
        <Field>
          <FieldLabel>{titleForLocale(locale, "语言", "Language")}</FieldLabel>
          <SegmentedControl
            className="!w-fit self-start"
            value={locale}
            onValueChange={(value) => setLocale(value)}
            options={[
              { value: "zh-CN", label: "简体中文" },
              { value: "en-US", label: "English" },
            ]}
          />
        </Field>
        <Field>
          <FieldLabel>
            {titleForLocale(locale, "站点名称", "Site name")}
          </FieldLabel>
          <Input
            value={siteName}
            onChange={(event) => onSiteNameChange(event.target.value)}
            placeholder="Lens"
          />
        </Field>
        <Field>
          <FieldLabel>
            {titleForLocale(locale, "Logo 地址", "Logo URL")}
          </FieldLabel>
          <Input
            value={siteLogoUrl}
            onChange={(event) => onSiteLogoUrlChange(event.target.value)}
            placeholder="https://example.com/logo.svg"
          />
        </Field>
      </FieldGroup>
      <div className="flex items-center gap-3 rounded-md border bg-muted/40 px-4 py-3">
        <span className="flex size-12 items-center justify-center overflow-hidden rounded-md border bg-background">
          {siteLogoUrl.trim() ? (
            <Image
              src={siteLogoUrl.trim()}
              alt={siteName || "logo"}
              width={48}
              height={48}
              className="size-12 object-contain"
              unoptimized
            />
          ) : (
            <ImageIcon className="text-muted-foreground" />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-foreground">
            {siteName.trim() || "Lens"}
          </div>
          <div className="truncate text-xs text-muted-foreground">
            {siteLogoUrl.trim() ||
              titleForLocale(locale, "未设置 Logo", "No logo configured")}
          </div>
        </div>
      </div>
    </>
  );
}
