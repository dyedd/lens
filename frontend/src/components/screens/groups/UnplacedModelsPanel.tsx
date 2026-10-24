import { ChevronDown, Trash2, Wand2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { ConfirmDeleteDialog } from "@/components/ui/ConfirmDeleteDialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { UnplacedModel } from "@/lib/api/groups";
import { cn } from "@/lib/classNames";
import type { SimilarGroupView } from "./groupTypes";
import { formatCredentialIdentity } from "./modelGroupFormatting";

type UnplacedCluster = {
  matchKey: string;
  modelNames: string[];
  models: UnplacedModel[];
  similarGroups: SimilarGroupView[];
};

interface UnplacedModelsPanelProps {
  locale: "zh-CN" | "en-US";
  unplacedModels: UnplacedModel[];
  busyId: string | null;
  /** Execution groups; route groups ignore match rules so cannot be joined. */
  joinableGroupIds: Set<string>;
  /** Join targets for the multi-select bulk action. */
  joinableGroups: Array<{ id: string; name: string }>;
  onAddModelsToGroup: (groupId: string, modelNames: string[]) => void;
  onCreateGroupForModels: (name: string, modelNames: string[]) => void;
  onCreateOwnGroups: (modelNames: string[]) => Promise<boolean>;
  onAutoPlace: () => void;
  onRemoveModels: (
    modelNames: string[],
    excludeFromOnboarding: boolean,
  ) => Promise<boolean>;
}

type RemoveRequest = {
  modelNames: string[];
  providerCount: number;
};

function buildUnplacedClusters(models: UnplacedModel[]): UnplacedCluster[] {
  const clusters = new Map<string, UnplacedCluster>();
  for (const model of models) {
    let cluster = clusters.get(model.match_key);
    if (!cluster) {
      cluster = {
        matchKey: model.match_key,
        modelNames: [],
        models: [],
        similarGroups: [],
      };
      clusters.set(model.match_key, cluster);
    }
    cluster.models.push(model);
    cluster.modelNames.push(model.model_name);
    model.similar_group_ids.forEach((id, index) => {
      if (cluster.similarGroups.some((group) => group.id === id)) return;
      cluster.similarGroups.push({
        id,
        name: model.similar_group_names[index] ?? id,
      });
    });
  }
  return [...clusters.values()];
}

function removalDescription(target: RemoveRequest | null, isZh: boolean) {
  const providerCount = target?.providerCount ?? 0;
  const names = target?.modelNames ?? [];
  if (names.length <= 1) {
    const name = names[0] ?? "";
    return isZh
      ? `从 ${providerCount} 个渠道的 API Key 中移除「${name}」。`
      : `Remove "${name}" from ${providerCount} channel API keys.`;
  }
  return isZh
    ? `移除 ${names.length} 个模型，涉及 ${providerCount} 个渠道的 API Key。`
    : `Remove ${names.length} models across ${providerCount} channel API keys.`;
}

function UnplacedModelName({
  model,
  locale,
}: {
  model: UnplacedModel;
  locale: "zh-CN" | "en-US";
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md px-1 font-mono text-xs hover:bg-muted"
        >
          {model.model_name}
          <span className="font-sans text-xs tabular-nums text-muted-foreground">
            ×{model.providers.length}
          </span>
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-md">
        <ul className="space-y-0.5">
          {model.providers.map((provider) => (
            <li key={`${provider.site_id}:${provider.credential_id}`}>
              {formatCredentialIdentity(provider, locale)}
            </li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}

/** List channel model names held back by match-key collisions. */
export function UnplacedModelsPanel({
  locale,
  unplacedModels,
  busyId,
  joinableGroupIds,
  joinableGroups,
  onAddModelsToGroup,
  onCreateGroupForModels,
  onCreateOwnGroups,
  onAutoPlace,
  onRemoveModels,
}: UnplacedModelsPanelProps) {
  const isZh = locale === "zh-CN";
  const clusters = useMemo(
    () => buildUnplacedClusters(unplacedModels),
    [unplacedModels],
  );
  const busy = Boolean(busyId);
  const [isOpen, setIsOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [removeTarget, setRemoveTarget] = useState<RemoveRequest | null>(null);
  const [excludeOnRemove, setExcludeOnRemove] = useState(true);
  const visibleNames = useMemo(
    () => new Set(unplacedModels.map((model) => model.model_name)),
    [unplacedModels],
  );
  const selectedModels = useMemo(
    () => unplacedModels.filter((model) => selected.has(model.model_name)),
    [selected, unplacedModels],
  );
  const selectedNames = selectedModels.map((model) => model.model_name);
  const allSelected =
    unplacedModels.length > 0 && selectedNames.length === unplacedModels.length;
  const someSelected = selectedNames.length > 0;

  useEffect(() => {
    setSelected((current) => {
      let changed = false;
      const next = new Set<string>();
      for (const name of current) {
        if (visibleNames.has(name)) next.add(name);
        else changed = true;
      }
      return changed ? next : current;
    });
  }, [visibleNames]);

  function selectNames(names: string[], checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      for (const name of names) {
        if (checked) next.add(name);
        else next.delete(name);
      }
      return next;
    });
  }

  function dropSelected(names: string[]) {
    setSelected((current) => {
      const next = new Set(current);
      for (const name of names) next.delete(name);
      return next;
    });
  }

  function requestRemoval(models: UnplacedModel[]) {
    if (!models.length) return;
    setExcludeOnRemove(true);
    setRemoveTarget({
      modelNames: models.map((model) => model.model_name),
      providerCount: models.reduce(
        (count, model) => count + model.providers.length,
        0,
      ),
    });
  }

  async function confirmRemove() {
    if (!removeTarget) return;
    const names = removeTarget.modelNames;
    if (await onRemoveModels(names, excludeOnRemove)) {
      setRemoveTarget(null);
      dropSelected(names);
    }
  }

  async function createSelectedGroups() {
    if (!selectedNames.length) return;
    const names = selectedNames;
    if (await onCreateOwnGroups(names)) dropSelected(names);
  }

  return (
    <section
      className="space-y-2 rounded-md bg-muted/35 p-3"
      aria-label={isZh ? "待分配模型" : "Models to assign"}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2">
          {isOpen ? (
            <Checkbox
              className="mt-0.5"
              checked={
                allSelected ? true : someSelected ? "indeterminate" : false
              }
              disabled={busy}
              aria-label={
                isZh ? "全选待分配模型" : "Select all models to assign"
              }
              onCheckedChange={(checked) =>
                selectNames([...visibleNames], checked === true)
              }
            />
          ) : null}
          <div className="min-w-0">
            <button
              type="button"
              aria-expanded={isOpen}
              onClick={() => setIsOpen((current) => !current)}
              className="flex items-center gap-1 text-xs font-medium"
            >
              <ChevronDown
                className={cn(
                  "size-3.5 text-muted-foreground transition-transform",
                  !isOpen && "-rotate-90",
                )}
              />
              {isZh ? "待分配模型" : "Models to assign"}
              <span className="tabular-nums text-muted-foreground">
                {unplacedModels.length}
              </span>
            </button>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">
          {someSelected ? (
            <>
              <Button
                type="button"
                variant="ghost"
                size="xs"
                disabled={busy}
                onClick={() => void createSelectedGroups()}
              >
                {isZh
                  ? `为每个模型建组 (${selectedNames.length})`
                  : `Create a group for each (${selectedNames.length})`}
              </Button>
              {joinableGroups.length ? (
                <DropdownMenu modal={false}>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="xs"
                      disabled={busy}
                    >
                      {isZh
                        ? `加入模型组 (${selectedNames.length})`
                        : `Join a group (${selectedNames.length})`}
                      <ChevronDown data-icon="inline-end" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {joinableGroups.map((group) => (
                      <DropdownMenuItem
                        key={group.id}
                        onSelect={() =>
                          onAddModelsToGroup(group.id, selectedNames)
                        }
                      >
                        {group.name}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : null}
              <Button
                type="button"
                variant="ghost"
                size="xs"
                disabled={busy}
                onClick={() => requestRemoval(selectedModels)}
              >
                <Trash2 data-icon="inline-start" />
                {isZh ? "从渠道删除" : "Remove"}
              </Button>
            </>
          ) : null}
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={onAutoPlace}
          >
            <Wand2 data-icon="inline-start" />
            {isZh ? "自动分配" : "Assign automatically"}
          </Button>
        </div>
      </div>
      {isOpen ? (
        <ul className="max-h-64 divide-y divide-border/60 overflow-y-auto">
          {clusters.map((cluster) => {
            const selectedInCluster = cluster.modelNames.filter((name) =>
              selected.has(name),
            ).length;
            return (
              <li
                key={cluster.matchKey}
                className="flex flex-wrap items-center gap-2 py-1.5"
              >
                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1">
                  <Checkbox
                    checked={
                      selectedInCluster === cluster.modelNames.length
                        ? true
                        : selectedInCluster > 0
                          ? "indeterminate"
                          : false
                    }
                    disabled={busy}
                    aria-label={
                      isZh
                        ? `选择 ${cluster.modelNames.join("、")}`
                        : `Select ${cluster.modelNames.join(", ")}`
                    }
                    onCheckedChange={(checked) =>
                      selectNames(cluster.modelNames, checked === true)
                    }
                  />
                  {cluster.models.map((model) => (
                    <UnplacedModelName
                      key={model.model_name}
                      model={model}
                      locale={locale}
                    />
                  ))}
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-1">
                  {cluster.models.length > 1 ? (
                    <DropdownMenu modal={false}>
                      <DropdownMenuTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="xs"
                          disabled={busy}
                        >
                          <Trash2 data-icon="inline-start" />
                          {isZh ? "从渠道删除" : "Remove"}
                          <ChevronDown data-icon="inline-end" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {cluster.models.map((model) => (
                          <DropdownMenuItem
                            key={model.model_name}
                            className="font-mono"
                            onSelect={() => requestRemoval([model])}
                          >
                            {model.model_name}
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : (
                    <Button
                      type="button"
                      variant="ghost"
                      size="xs"
                      disabled={busy}
                      onClick={() => requestRemoval(cluster.models)}
                    >
                      <Trash2 data-icon="inline-start" />
                      {isZh ? "从渠道删除" : "Remove"}
                    </Button>
                  )}
                  {cluster.similarGroups
                    .filter((group) => joinableGroupIds.has(group.id))
                    .map((group) => (
                      <Button
                        key={group.id}
                        type="button"
                        variant="ghost"
                        size="xs"
                        disabled={busy}
                        onClick={() =>
                          onAddModelsToGroup(group.id, cluster.modelNames)
                        }
                      >
                        {isZh ? "加入" : "Join"}
                        <span className="font-mono">{group.name}</span>
                      </Button>
                    ))}
                  {cluster.models.length > 1 ? (
                    <>
                      <DropdownMenu modal={false}>
                        <DropdownMenuTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="xs"
                            disabled={busy}
                          >
                            {isZh ? "合并为一组" : "Group together"}
                            <ChevronDown data-icon="inline-end" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuLabel className="text-xs text-muted-foreground">
                            {isZh ? "选择组名" : "Group name"}
                          </DropdownMenuLabel>
                          {cluster.modelNames.map((name) => (
                            <DropdownMenuItem
                              key={name}
                              className="font-mono"
                              onSelect={() =>
                                onCreateGroupForModels(name, cluster.modelNames)
                              }
                            >
                              {name}
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                      <DropdownMenu modal={false}>
                        <DropdownMenuTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="xs"
                            disabled={busy}
                          >
                            {isZh ? "单独建组" : "Own group"}
                            <ChevronDown data-icon="inline-end" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          {cluster.modelNames.map((name) => (
                            <DropdownMenuItem
                              key={name}
                              className="font-mono"
                              onSelect={() =>
                                onCreateGroupForModels(name, [name])
                              }
                            >
                              {name}
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </>
                  ) : (
                    <Button
                      type="button"
                      variant="ghost"
                      size="xs"
                      disabled={busy}
                      onClick={() =>
                        onCreateGroupForModels(
                          cluster.modelNames[0],
                          cluster.modelNames,
                        )
                      }
                    >
                      {isZh ? "单独建组" : "Own group"}
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
      <ConfirmDeleteDialog
        open={Boolean(removeTarget)}
        locale={locale}
        title={
          isZh
            ? removeTarget && removeTarget.modelNames.length > 1
              ? "从渠道删除所选模型"
              : "从渠道删除模型"
            : removeTarget && removeTarget.modelNames.length > 1
              ? "Remove selected models"
              : "Remove model from channels"
        }
        description={removalDescription(removeTarget, isZh)}
        isBusy={busy}
        onOpenChange={(open) => {
          if (!open) setRemoveTarget(null);
        }}
        onConfirm={() => void confirmRemove()}
      >
        <label
          htmlFor="unplaced-exclude-on-remove"
          className="flex items-start gap-2 rounded-md bg-muted/35 p-2.5 text-xs text-muted-foreground"
        >
          <Checkbox
            id="unplaced-exclude-on-remove"
            className="mt-0.5"
            checked={excludeOnRemove}
            onCheckedChange={(checked) => setExcludeOnRemove(checked === true)}
          />
          <span>
            {isZh
              ? "同时加入排除正则，避免下次同步重新接入这些模型。"
              : "Add exclusion regexes so the next sync does not onboard these models again."}
          </span>
        </label>
      </ConfirmDeleteDialog>
    </section>
  );
}
