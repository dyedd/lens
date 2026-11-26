import {
  Bot,
  Code2,
  Globe,
  HelpCircle,
  MessageSquare,
  Server,
  Sparkles,
  Terminal,
} from "lucide-react";
import type { AttributionDimension } from "@/lib/api/overview";
import { cn } from "@/lib/classNames";
import { getModelGroupAvatar } from "@/lib/ModelIcons";

function OpenCodeGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <rect
        x="2"
        y="2"
        width="12"
        height="12"
        rx="2.5"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <rect x="5" y="5.5" width="6" height="5" rx="1" fill="currentColor" />
    </svg>
  );
}

function CursorGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M3.2 2.4 13 7.2 8.4 8.7 6.8 13.4 3.2 2.4Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function AgentGlyph({ agentKey, size }: { agentKey: string; size: number }) {
  const boxStyle = { width: size, height: size };
  const iconClass = "size-3.5 text-foreground/75";

  if (agentKey === "codex" || agentKey === "openai_sdk") {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center"
        style={boxStyle}
      >
        <img
          src="/brand-icons/gpt.svg"
          alt=""
          width={size}
          height={size}
          className="h-full w-full scale-[0.9] object-contain dark:invert"
        />
      </span>
    );
  }
  if (agentKey === "claude_code" || agentKey === "anthropic_sdk") {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center"
        style={boxStyle}
      >
        <img
          src="/brand-icons/claude.svg"
          alt=""
          width={size}
          height={size}
          className="h-full w-full scale-[0.92] object-contain dark:invert"
        />
      </span>
    );
  }
  if (agentKey === "gemini_cli") {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center"
        style={boxStyle}
      >
        <img
          src="/brand-icons/gemini.svg"
          alt=""
          width={size}
          height={size}
          className="h-full w-full scale-[0.9] object-contain"
        />
      </span>
    );
  }

  let glyph = <Globe className={cn(iconClass, "text-muted-foreground")} />;
  if (agentKey === "opencode") {
    glyph = <OpenCodeGlyph className="size-3.5 text-foreground" />;
  } else if (agentKey === "cursor") {
    glyph = <CursorGlyph className="size-3.5 text-foreground" />;
  } else if (agentKey === "python_httpx") {
    glyph = <Code2 className={iconClass} />;
  } else if (agentKey === "cline" || agentKey === "roo_code") {
    glyph = <Bot className={iconClass} />;
  } else if (agentKey === "cherry_studio") {
    glyph = <Sparkles className={iconClass} />;
  } else if (agentKey === "chatbox") {
    glyph = <MessageSquare className={iconClass} />;
  } else if (agentKey === "openclaw" || agentKey === "curl") {
    glyph = <Terminal className={iconClass} />;
  } else if (agentKey === "unknown") {
    glyph = <HelpCircle className={cn(iconClass, "text-muted-foreground")} />;
  }

  return (
    <span
      className="inline-flex shrink-0 items-center justify-center"
      style={boxStyle}
      aria-hidden="true"
    >
      {glyph}
    </span>
  );
}

/** Render a unified icon for a model, channel, or agent attribution item. */
export function AttributionIcon({
  dimension,
  itemKey,
  size = 16,
}: {
  dimension: AttributionDimension;
  itemKey: string;
  size?: number;
}) {
  if (dimension === "model") {
    const Avatar = getModelGroupAvatar(itemKey);
    return <Avatar size={size} />;
  }
  if (dimension === "channel") {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center text-muted-foreground"
        style={{ width: size, height: size }}
        aria-hidden="true"
      >
        <Server className="size-3.5" />
      </span>
    );
  }
  return <AgentGlyph agentKey={itemKey} size={size} />;
}

/** Return localized display label for attribution items across dimensions. */
export function formatAttributionDisplayLabel(
  key: string,
  label: string,
  dimension: AttributionDimension,
  zh: boolean,
) {
  if (dimension === "agent") {
    if (key === "other") return zh ? "其他客户端" : "Other";
    if (!key || key === "unknown") return zh ? "未知客户端" : "Unknown";
    return label || key;
  }
  if (key) return label;
  return dimension === "model"
    ? zh
      ? "未知模型"
      : "Unknown model"
    : zh
      ? "未知渠道"
      : "Unknown channel";
}
