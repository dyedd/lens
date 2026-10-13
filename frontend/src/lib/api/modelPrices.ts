import type { ProtocolKind } from "./protocols";
/** Token prices that replace the base prices above an input-token threshold. */
export type ModelPriceContextTier = {
  above_input_tokens: number;
  input_price_per_million: number;
  output_price_per_million: number;
  cache_read_price_per_million: number;
  cache_write_price_per_million: number;
};
export type ModelPriceItem = {
  model_key: string;
  display_name: string;
  protocols: ProtocolKind[];
  input_price_per_million: number;
  image_input_price_per_million: number;
  output_price_per_million: number;
  cache_read_price_per_million: number;
  cache_write_price_per_million: number;
  image_price_per_image: number;
  pricing_mode: "free" | "tokens" | "non_tokens";
  manual_override: boolean;
  context_tiers: ModelPriceContextTier[];
};
