import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LockKeyhole, Pencil, RefreshCw, Search, Unlock } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { TablePagination } from "@/components/ui/Pagination";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { apiRequest } from "@/lib/api/client";
import type { ModelGroup } from "@/lib/api/groups";
import { type Locale, useI18n } from "@/lib/I18nContext";
import { getModelGroupAvatar } from "@/lib/ModelIcons";
import {
  formatMoney,
  modelGroupErrorMessage,
} from "./groups/modelGroupFormatting";

const PRICE_FIELDS = [
  ["input_price_per_million", "输入", "Input"],
  ["image_input_price_per_million", "图片输入", "Image input"],
  ["output_price_per_million", "输出", "Output"],
  ["cache_read_price_per_million", "缓存读取", "Cache read"],
  ["cache_write_price_per_million", "缓存写入", "Cache write"],
  ["image_price_per_image", "每张价格", "Per image"],
] as const;
const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;
const TOKEN_PRICE_FIELDS = PRICE_FIELDS.filter(
  ([key]) => key !== "image_price_per_image",
);
const IMAGE_PRICE_FIELDS = PRICE_FIELDS.filter(
  ([key]) => key === "image_price_per_image",
);

function PriceEditor({
  group,
  locale,
  onClose,
  onSaved,
}: {
  group: ModelGroup;
  locale: Locale;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const isChinese = locale === "zh-CN";
  const [mode, setMode] = useState(group.pricing_mode);
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(PRICE_FIELDS.map(([key]) => [key, String(group[key])])),
  );
  const [saving, setSaving] = useState(false);
  const hasImageMember = group.items.some(
    (item) => item.protocol === "openai_image",
  );
  const fields = PRICE_FIELDS.filter(([key]) =>
    mode === "free"
      ? false
      : mode === "non_tokens"
        ? key === "image_price_per_image"
        : key !== "image_price_per_image" &&
          (key !== "image_input_price_per_million" || hasImageMember),
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const parsed = Object.fromEntries(
      PRICE_FIELDS.map(([key]) => [
        key,
        mode === "free" ? 0 : Number(values[key]),
      ]),
    );
    if (
      PRICE_FIELDS.some(
        ([key]) => !Number.isFinite(parsed[key]) || parsed[key] < 0,
      )
    ) {
      toast.error(
        isChinese
          ? "价格必须是大于等于 0 的数字"
          : "Prices must be numbers greater than or equal to 0",
      );
      return;
    }
    setSaving(true);
    try {
      await apiRequest(
        `/admin/model-prices/${encodeURIComponent(group.name)}`,
        {
          method: "PUT",
          body: JSON.stringify({
            model_key: group.name,
            display_name: group.name,
            ...parsed,
            pricing_mode: mode,
          }),
        },
      );
      await onSaved();
      onClose();
    } catch (error) {
      toast.error(
        modelGroupErrorMessage(
          error,
          isChinese ? "保存价格失败" : "Failed to save price",
        ),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !saving && onClose()}>
      <DialogContent className="flex max-h-[min(86dvh,760px)] flex-col gap-0 overflow-hidden p-0 sm:max-w-[620px]">
        <DialogHeader className="shrink-0 space-y-1.5 gap-0 px-4 py-4 pr-12">
          <DialogTitle>
            {isChinese ? "模型基础价格" : "Model base pricing"}
          </DialogTitle>
          <DialogDescription>
            {isChinese
              ? "设置模型的计费模式与基础单价。"
              : "Set the model's billing mode and base rates."}
          </DialogDescription>
        </DialogHeader>
        <form className="flex min-h-0 flex-1 flex-col" onSubmit={submit}>
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-2">
            <Field className="gap-1">
              <FieldLabel
                htmlFor="price-model"
                className="text-xs text-muted-foreground"
              >
                {isChinese ? "模型" : "Model"}
              </FieldLabel>
              <Input id="price-model" value={group.name} readOnly />
            </Field>
            <Field className="gap-1 sm:w-[calc(50%-10px)]">
              <FieldLabel
                htmlFor="price-mode"
                className="text-xs text-muted-foreground"
              >
                {isChinese ? "计费模式" : "Billing mode"}
              </FieldLabel>
              <Select
                value={mode}
                disabled={saving}
                onValueChange={(value) => {
                  if (
                    value === "free" ||
                    value === "tokens" ||
                    value === "non_tokens"
                  )
                    setMode(value);
                }}
              >
                <SelectTrigger id="price-mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="free">
                      {isChinese ? "免费" : "Free"}
                    </SelectItem>
                    <SelectItem value="tokens">
                      {isChinese ? "Token 计费" : "Token billing"}
                    </SelectItem>
                    {hasImageMember ? (
                      <SelectItem value="non_tokens">
                        {isChinese ? "按张计费" : "Per-image billing"}
                      </SelectItem>
                    ) : null}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <div
              className={
                mode === "tokens" ? "grid grid-cols-2 gap-5" : "grid gap-5"
              }
            >
              {fields.map(([key, zh, en]) => (
                <Field key={key} className="gap-1">
                  <FieldLabel
                    htmlFor={`price-${key}`}
                    className="text-xs text-muted-foreground"
                  >
                    {isChinese ? zh : en}
                    {mode === "tokens"
                      ? "（USD / 1M tokens）"
                      : isChinese
                        ? "（USD / 张）"
                        : " (USD / image)"}
                  </FieldLabel>
                  <Input
                    id={`price-${key}`}
                    type="number"
                    required
                    min="0"
                    step="any"
                    inputMode="decimal"
                    value={values[key]}
                    disabled={saving}
                    onChange={(event) =>
                      setValues((current) => ({
                        ...current,
                        [key]: event.target.value,
                      }))
                    }
                  />
                </Field>
              ))}
            </div>
            {mode === "tokens" && hasImageMember ? (
              <p className="text-xs leading-5 text-muted-foreground">
                {isChinese
                  ? "输入不含图片 Token；图片 Token 按“图片输入”单价计费。"
                  : "Input excludes image tokens, which use the Image input rate."}
              </p>
            ) : null}
            <p className="text-xs leading-5 text-muted-foreground">
              {isChinese
                ? "保存后会锁定为手动价格，自动同步不会覆盖。点击解锁图标可恢复自动同步。"
                : "Saving locks this model to manual pricing. Automatic sync skips it until you restore automatic sync."}
            </p>
          </div>
          <DialogFooter className="shrink-0 px-4 pt-3 pb-4">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={saving}
              onClick={onClose}
            >
              {isChinese ? "取消" : "Cancel"}
            </Button>
            <Button type="submit" size="sm" disabled={saving}>
              {isChinese ? "保存" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ModelPricesScreen() {
  const { locale } = useI18n();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<ModelGroup | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] =
    useState<(typeof PAGE_SIZE_OPTIONS)[number]>(25);
  const groups = useQuery({
    queryKey: ["groups"],
    queryFn: () => apiRequest<ModelGroup[]>("/admin/model-groups"),
  });
  const isChinese = locale === "zh-CN";
  const rows = (groups.data ?? []).filter(
    (group) =>
      !group.route_group_id &&
      group.name.toLowerCase().includes(search.trim().toLowerCase()),
  );
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const pagedRows = useMemo(
    () => rows.slice((safePage - 1) * pageSize, safePage * pageSize),
    [rows, pageSize, safePage],
  );
  const rowsByMode = (mode: ModelGroup["pricing_mode"]) =>
    pagedRows.filter((group) => group.pricing_mode === mode);

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["groups"] });
  }

  async function syncPrices() {
    if (syncing) return;
    setSyncing(true);
    try {
      await apiRequest("/admin/model-price-sync-jobs", { method: "POST" });
      await refresh();
      toast.success(isChinese ? "模型价格已同步" : "Model prices synced");
    } catch (error) {
      toast.error(
        modelGroupErrorMessage(
          error,
          isChinese ? "同步价格失败" : "Failed to sync prices",
        ),
      );
    } finally {
      setSyncing(false);
    }
  }

  return (
    <section className="space-y-3 pb-10">
      <div className="flex h-10 items-center px-1">
        <h1 className="text-sm font-semibold">
          {isChinese ? "计费" : "Billing"}
        </h1>
      </div>
      <div className="flex min-h-10 flex-nowrap items-center gap-1.5 overflow-x-auto px-0.5 py-1">
        <div className="flex min-w-0 flex-1 items-center">
          <div className="relative min-w-[220px] flex-1 md:max-w-[320px]">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="bg-background pl-8"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder={isChinese ? "搜索模型" : "Search models"}
            />
          </div>
        </div>
        <div className="ml-auto flex shrink-0 items-center">
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            disabled={groups.isFetching || syncing}
            onClick={() => void syncPrices()}
            aria-label={isChinese ? "同步价格" : "Sync prices"}
            title={isChinese ? "同步价格" : "Sync prices"}
          >
            <RefreshCw
              className={
                groups.isFetching || syncing ? "animate-spin" : undefined
              }
            />
          </Button>
        </div>
      </div>
      {(["free", "tokens", "non_tokens"] as const).map((mode) => {
        const modeRows = rowsByMode(mode);
        if (!modeRows.length) return null;
        const fields =
          mode === "tokens"
            ? TOKEN_PRICE_FIELDS
            : mode === "non_tokens"
              ? IMAGE_PRICE_FIELDS
              : [];
        return (
          <div key={mode} className="space-y-1.5">
            <h2 className="px-1 text-xs font-medium text-muted-foreground">
              {mode === "free"
                ? isChinese
                  ? "免费"
                  : "Free"
                : mode === "tokens"
                  ? isChinese
                    ? "按 Token 计费"
                    : "Token billing"
                  : isChinese
                    ? "按张计费"
                    : "Per-image billing"}
            </h2>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[210px]">
                    {isChinese ? "模型" : "Model"}
                  </TableHead>
                  {fields.map(([key, zh, en]) => (
                    <TableHead key={key} className="text-right">
                      <div>{isChinese ? zh : en}</div>
                      <div className="font-normal">
                        {key === "image_price_per_image"
                          ? isChinese
                            ? "USD / 张"
                            : "USD / image"
                          : "USD / 1M tokens"}
                      </div>
                    </TableHead>
                  ))}
                  <TableHead className="w-[56px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {modeRows.map((group) => {
                  const Avatar = getModelGroupAvatar(group.name);
                  return (
                    <TableRow key={group.id}>
                      <TableCell className="py-1.5">
                        <div className="flex h-7 min-w-0 items-center gap-2">
                          <Avatar size={16} />
                          <span className="truncate text-xs font-medium">
                            {group.name}
                          </span>
                          {group.manual_override ? (
                            <LockKeyhole className="size-3 shrink-0 text-muted-foreground" />
                          ) : null}
                        </div>
                      </TableCell>
                      {fields.map(([key]) => (
                        <TableCell
                          key={key}
                          className="py-1.5 text-right tabular-nums"
                        >
                          {key === "image_input_price_per_million" &&
                          !group.items.some(
                            (item) => item.protocol === "openai_image",
                          ) ? (
                            <span className="text-muted-foreground">—</span>
                          ) : (
                            formatMoney(group[key])
                          )}
                        </TableCell>
                      ))}
                      <TableCell className="py-1.5 text-right">
                        {group.manual_override ? (
                          <Button
                            type="button"
                            size="icon-sm"
                            variant="ghost"
                            className="h-7 w-7 text-muted-foreground shadow-none"
                            aria-label={`${isChinese ? "恢复自动同步" : "Restore automatic sync"} ${group.name}`}
                            onClick={async () => {
                              try {
                                await apiRequest(
                                  `/admin/model-prices/${encodeURIComponent(group.name)}/restore-automatic`,
                                  { method: "POST" },
                                );
                                await refresh();
                                toast.success(
                                  isChinese
                                    ? "已恢复自动同步"
                                    : "Automatic sync restored",
                                );
                              } catch (error) {
                                toast.error(
                                  modelGroupErrorMessage(
                                    error,
                                    isChinese
                                      ? "恢复自动同步失败"
                                      : "Failed to restore automatic sync",
                                  ),
                                );
                              }
                            }}
                          >
                            <Unlock className="size-3.5 stroke-1" />
                          </Button>
                        ) : null}
                        <Button
                          type="button"
                          size="icon-sm"
                          variant="ghost"
                          className="h-7 w-7 text-muted-foreground shadow-none"
                          aria-label={`${isChinese ? "编辑" : "Edit"} ${group.name}`}
                          onClick={() => setEditing(group)}
                        >
                          <Pencil className="size-3.5 stroke-1" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        );
      })}
      {!groups.isLoading && rows.length === 0 ? (
        <Table>
          <TableBody>
            <TableRow>
              <TableCell
                colSpan={2}
                className="h-32 text-center text-muted-foreground"
              >
                {isChinese ? "暂无计费模型" : "No pricing models"}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      ) : null}
      <TablePagination
        locale={locale}
        total={rows.length}
        page={safePage}
        pageCount={pageCount}
        pageSize={pageSize}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size as (typeof PAGE_SIZE_OPTIONS)[number]);
          setPage(1);
        }}
      />
      {editing ? (
        <PriceEditor
          group={editing}
          locale={locale}
          onClose={() => setEditing(null)}
          onSaved={refresh}
        />
      ) : null}
    </section>
  );
}
