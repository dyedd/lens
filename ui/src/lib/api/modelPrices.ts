import type { ProtocolKind } from "./protocols";
export type ModelPriceItem = {
  model_key: string;
  display_name: string;
  protocols: ProtocolKind[];
  input_price_per_million: number;
  output_price_per_million: number;
  cache_read_price_per_million: number;
  cache_write_price_per_million: number;
  image_price_per_image: number;
  pricing_mode: "tokens" | "non_tokens";
};
export type ModelPriceListResponse = {
  items: ModelPriceItem[];
  last_synced_at?: string | null;
};
export type ModelPriceUpdatePayload = {
  model_key: string;
  display_name: string;
  input_price_per_million: number;
  output_price_per_million: number;
  cache_read_price_per_million: number;
  cache_write_price_per_million: number;
  image_price_per_image: number;
  pricing_mode?: "tokens" | "non_tokens";
};
