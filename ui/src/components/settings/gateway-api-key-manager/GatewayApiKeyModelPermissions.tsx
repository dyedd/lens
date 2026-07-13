import { ChevronsUpDown } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/Command";
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/Field";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import { Switch } from "@/components/ui/Switch";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import {
  protocolSummary,
  type GatewayModelGroupOption,
} from "./gatewayApiKeyUtils";

type GatewayApiKeyModelPermissionsProps = {
  locale: Locale;
  isRestrictionEnabled: boolean;
  allowedModels: string[];
  modelGroupOptions: GatewayModelGroupOption[];
  pickerOpen: boolean;
  onPickerOpenChange: (open: boolean) => void;
  onRestrictionEnabledChange: (enabled: boolean) => void;
  onToggleAllowedModel: (name: string) => void;
};

/** Renders the gateway key model-group restriction controls. */
export function GatewayApiKeyModelPermissions({
  locale,
  isRestrictionEnabled,
  allowedModels,
  modelGroupOptions,
  pickerOpen,
  onPickerOpenChange,
  onRestrictionEnabledChange,
  onToggleAllowedModel,
}: GatewayApiKeyModelPermissionsProps) {
  const permissionSummary = !isRestrictionEnabled
    ? titleForLocale(locale, "全部当前模型组", "All current model groups")
    : allowedModels.length > 0
      ? allowedModels.join(", ")
      : titleForLocale(locale, "请选择模型组", "Select model groups");

  return (
    <FieldSet>
      <FieldLegend variant="label">
        {titleForLocale(locale, "允许模型组", "Allowed model groups")}
      </FieldLegend>

      <Field
        orientation="horizontal"
        className="items-center justify-between rounded-lg border bg-muted/20 px-3 py-3"
      >
        <FieldContent>
          <FieldLabel className="w-auto">
            {titleForLocale(
              locale,
              "仅允许选定模型组",
              "Restrict to selected groups",
            )}
          </FieldLabel>
          <FieldDescription>
            {titleForLocale(
              locale,
              "关闭时可调用当前全部启用模型组",
              "Disabled means the key can use every enabled model group",
            )}
          </FieldDescription>
        </FieldContent>
        <Switch
          checked={isRestrictionEnabled}
          onCheckedChange={(checked) =>
            onRestrictionEnabledChange(Boolean(checked))
          }
        />
      </Field>

      <Field data-disabled={!isRestrictionEnabled}>
        <FieldLabel>
          {titleForLocale(locale, "模型组", "Model groups")}
        </FieldLabel>
        <Popover open={pickerOpen} onOpenChange={onPickerOpenChange}>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              className="w-full justify-between"
              disabled={!isRestrictionEnabled}
            >
              <span className="truncate text-left">{permissionSummary}</span>
              <ChevronsUpDown className="text-muted-foreground" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            align="start"
            className="w-[calc(100vw-2rem)] p-0 sm:w-[360px]"
          >
            <Command>
              <CommandInput
                placeholder={titleForLocale(
                  locale,
                  "搜索模型组...",
                  "Search model groups...",
                )}
              />
              <CommandList>
                <CommandEmpty>
                  {modelGroupOptions.length > 0
                    ? titleForLocale(
                        locale,
                        "没有匹配的模型组",
                        "No matching model groups",
                      )
                    : titleForLocale(
                        locale,
                        "当前没有可用模型组",
                        "No model groups available",
                      )}
                </CommandEmpty>
                <CommandGroup
                  heading={titleForLocale(
                    locale,
                    "当前启用模型组",
                    "Enabled model groups",
                  )}
                >
                  {modelGroupOptions.map((option) => {
                    const isChecked = allowedModels.includes(option.name);
                    return (
                      <CommandItem
                        key={option.name}
                        value={`${option.name} ${protocolSummary(locale, option.protocols)} ${option.channelNames.join(" ")}`}
                        onSelect={() => onToggleAllowedModel(option.name)}
                        className="items-start gap-3"
                      >
                        <Checkbox
                          checked={isChecked}
                          className="mt-0.5 pointer-events-none"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="truncate font-medium text-foreground">
                            {option.name}
                          </div>
                          <div className="truncate text-xs text-muted-foreground">
                            {protocolSummary(locale, option.protocols)} ·{" "}
                            {titleForLocale(
                              locale,
                              `${option.enabledItemCount} 个启用成员`,
                              `${option.enabledItemCount} enabled members`,
                            )}
                          </div>
                        </div>
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
        <FieldDescription>
          {isRestrictionEnabled
            ? titleForLocale(
                locale,
                "权限来源于当前启用模型组；留空将无法保存",
                "Permissions come from currently enabled model groups; choose at least one",
              )
            : titleForLocale(
                locale,
                "当前为全部放行模式",
                "The key can currently access all model groups",
              )}
        </FieldDescription>
        {isRestrictionEnabled && allowedModels.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {allowedModels.map((modelName) => (
              <Badge key={modelName} variant="outline">
                {modelName}
              </Badge>
            ))}
          </div>
        ) : null}
      </Field>
    </FieldSet>
  );
}
