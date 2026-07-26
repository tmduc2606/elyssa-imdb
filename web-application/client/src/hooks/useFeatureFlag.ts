import { FEATURE_FLAGS, type FeatureFlagKey } from "@/lib/constants";

export function useFeatureFlag(key: FeatureFlagKey): boolean {
  return FEATURE_FLAGS[key];
}
