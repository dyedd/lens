import Image from "next/image";
import { cn } from "@/lib/utils";

type AvatarProps = {
  size?: number;
};

type AvatarComponent = (props: AvatarProps) => React.JSX.Element;

type BrandIconDefinition = {
  key: string;
  label: string;
  prefixes: string[];
  src: string;
  imageClassName?: string;
  invertInDark?: boolean;
};

const BRAND_ICONS: BrandIconDefinition[] = [
  {
    key: "openai",
    label: "OpenAI",
    prefixes: ["gpt-", "o1", "o3", "o4", "chatgpt", "openai", "text-embedding"],
    src: "/brand-icons/gpt.svg",
    imageClassName: "scale-[0.94]",
    invertInDark: true,
  },
  {
    key: "claude",
    label: "Claude",
    prefixes: ["claude", "anthropic"],
    src: "/brand-icons/claude.svg",
    imageClassName: "scale-[0.96]",
    invertInDark: true,
  },
  {
    key: "gemini",
    label: "Gemini",
    prefixes: ["gemini", "gemma", "google"],
    src: "/brand-icons/gemini.svg",
    imageClassName: "scale-[0.94]",
  },
  {
    key: "deepseek",
    label: "DeepSeek",
    prefixes: ["deepseek"],
    src: "/brand-icons/deepseek.svg",
    imageClassName: "scale-[0.94]",
  },
  {
    key: "qwen",
    label: "Qwen",
    prefixes: ["qwen", "qwq", "alibaba"],
    src: "/brand-icons/qwen.svg",
    imageClassName: "scale-[0.94]",
  },
  {
    key: "kimi",
    label: "Kimi",
    prefixes: ["moonshot", "kimi"],
    src: "/brand-icons/kimi.svg",
    imageClassName: "scale-[0.94]",
    invertInDark: true,
  },
  {
    key: "glm",
    label: "GLM",
    prefixes: ["glm", "chatglm", "zhipu", "z-ai", "zai-org"],
    src: "/brand-icons/glm.svg",
    imageClassName: "scale-[0.94]",
    invertInDark: true,
  },
  {
    key: "minimax",
    label: "MiniMax",
    prefixes: ["minimax", "abab", "minmax"],
    src: "/brand-icons/minmax.svg",
    imageClassName: "scale-[0.92]",
  },
];

const fallbackIcon: BrandIconDefinition = {
  key: "fallback",
  label: "",
  prefixes: [],
  src: "/logo.svg",
  imageClassName: "scale-[0.72]",
};

function createAvatar(definition: BrandIconDefinition): AvatarComponent {
  return function BrandAvatar({ size = 40 }: AvatarProps) {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center"
        style={{ width: size, height: size }}
      >
        <Image
          src={definition.src}
          alt=""
          width={size}
          height={size}
          className={cn(
            "h-full w-full object-contain",
            definition.imageClassName,
            definition.invertInDark && "dark:invert",
          )}
        />
      </span>
    );
  };
}

const iconEntries = BRAND_ICONS.map((item) => ({
  key: item.key,
  label: item.label,
  prefixes: item.prefixes,
  Avatar: createAvatar(item),
}));

const fallbackAvatar = createAvatar(fallbackIcon);

function normalizeModelNameForFamily(name: string) {
  return (name.includes("/") ? name.split("/")[1] : name).trim().toLowerCase();
}

function getRawModelPrefix(value: string) {
  const normalized = value.trim().toLowerCase();
  const match = /^[a-z0-9]+/.exec(normalized);
  return match?.[0] || normalized;
}

function getModelFamilyDefinition(name: string) {
  const normalized = normalizeModelNameForFamily(name);
  for (const item of iconEntries) {
    if (item.prefixes.some((prefix) => normalized.startsWith(prefix))) {
      return item;
    }
  }
  return null;
}

export function getModelFamilyKey(name: string) {
  return getModelFamilyDefinition(name)?.key || getRawModelPrefix(name);
}

export function getModelFamilyLabel(name: string) {
  const definition = getModelFamilyDefinition(name);
  if (definition) return definition.label;
  const prefix = getRawModelPrefix(name);
  return prefix ? prefix[0].toUpperCase() + prefix.slice(1) : prefix;
}

export function getModelGroupAvatar(name: string): AvatarComponent {
  const definition = getModelFamilyDefinition(name);
  if (definition) {
    return definition.Avatar;
  }
  return fallbackAvatar;
}

export function ModelAvatar({ name, size }: { name: string; size?: number }) {
  const avatarFn = getModelGroupAvatar(name);
  return avatarFn({ size });
}
