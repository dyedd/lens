import { ChevronDown, Wand2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
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
import { protocolLabel } from "@/lib/protocols";
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
  onAddModelsToGroup: (groupId: string, modelNames: string[]) => void;
  onCreateGroupForModels: (name: string, modelNames: string[]) => void;
  onAutoPlace: () => void;
}

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
          <span className="font-sans text-[11px] tabular-nums text-muted-foreground">
            ×{model.providers.length}
          </span>
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-md">
        <ul className="space-y-0.5">
          {model.providers.map((provider) => (
            <li key={`${provider.site_id}:${provider.credential_id}`}>
              {formatCredentialIdentity(provider, locale)}
              {provider.protocols.length
                ? ` · ${provider.protocols
                    .map((protocol) => protocolLabel(protocol, locale))
                    .join("/")}`
                : ""}
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
  onAddModelsToGroup,
  onCreateGroupForModels,
  onAutoPlace,
}: UnplacedModelsPanelProps) {
  const clusters = useMemo(
    () => buildUnplacedClusters(unplacedModels),
    [unplacedModels],
  );
  const busy = Boolean(busyId);
  const [isOpen, setIsOpen] = useState(false);

  return (
    <section
      className="space-y-2 rounded-md bg-muted/35 p-3"
      aria-label={locale === "zh-CN" ? "待放置模型" : "Unplaced models"}
    >
      <div className="flex items-start justify-between gap-3">
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
            {locale === "zh-CN" ? "待放置" : "Unplaced"}
            <span className="tabular-nums text-muted-foreground">
              {unplacedModels.length}
            </span>
          </button>
          {isOpen ? (
            <p className="text-xs text-muted-foreground">
              {locale === "zh-CN"
                ? "这些模型名与已有模型组或彼此只差大小写或符号，未自动建组，请选择归属。"
                : "These names differ from existing groups or each other only by case or symbols, so they were not auto-grouped."}
            </p>
          ) : null}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="shrink-0"
          disabled={busy}
          onClick={onAutoPlace}
        >
          <Wand2 data-icon="inline-start" />
          {locale === "zh-CN" ? "自动放置" : "Auto place"}
        </Button>
      </div>
      {isOpen ? (
        <ul className="max-h-64 divide-y divide-border/60 overflow-y-auto">
          {clusters.map((cluster) => (
            <li
              key={cluster.matchKey}
              className="flex flex-wrap items-center gap-2 py-1.5"
            >
              <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1">
                {cluster.models.map((model) => (
                  <UnplacedModelName
                    key={model.model_name}
                    model={model}
                    locale={locale}
                  />
                ))}
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-1">
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
                      {locale === "zh-CN" ? "加入" : "Join"}
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
                          {locale === "zh-CN" ? "合并建组" : "Group together"}
                          <ChevronDown data-icon="inline-end" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuLabel className="text-[10px] text-muted-foreground">
                          {locale === "zh-CN" ? "选择组名" : "Group name"}
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
                          {locale === "zh-CN" ? "单独建组" : "Own group"}
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
                    {locale === "zh-CN" ? "单独建组" : "Own group"}
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
