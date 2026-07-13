import { toast } from "sonner";
import {
  invalidModelProtocolCount,
  invalidProtocolBaseUrlCount,
  type FormState,
  type Locale,
} from "./channelShared";

export function validateChannelForm(
  form: FormState,
  duplicatedConfigCount: number,
  locale: Locale,
) {
  if (invalidProtocolBaseUrlCount(form)) {
    toast.error(
      locale === "zh-CN"
        ? "组合地址来源无效"
        : "Combination Base URL is invalid",
    );
    return false;
  }
  if (duplicatedConfigCount) {
    toast.error(
      locale === "zh-CN"
        ? "同一个渠道内不允许重复地址来源、密钥和协议"
        : "Duplicate Base URL, key, and protocol sets are not allowed in one channel",
    );
    return false;
  }
  if (invalidModelProtocolCount(form)) {
    toast.error(
      locale === "zh-CN"
        ? "请为每个模型选择至少一个有效协议"
        : "Select at least one valid protocol for every model",
    );
    return false;
  }
  return true;
}
