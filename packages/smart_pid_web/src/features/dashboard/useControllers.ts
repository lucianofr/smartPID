import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { ControllerResponse } from '@/api/types';
import type { Scale } from '@/lib/scale';

/**
 * Controller roster. Uses the canonical `queryKeys.controllers` entry so the
 * §7 resync runner's `setQueryData` is visible here without a refetch.
 */
export function useControllers(): UseQueryResult<ControllerResponse[]> {
  return useQuery({
    queryKey: queryKeys.controllers,
    queryFn: () => endpoints.controllers(),
  });
}

/** PV engineering scale; `pv_scale` is optional on the wire (schema default). */
export function pvScale(controller: ControllerResponse): Scale {
  const s = controller.pv_scale;
  return { euMin: s?.eu_min ?? 0, euMax: s?.eu_max ?? 100, unit: s?.unit ?? '' };
}

/** CO is always a valve percentage — the right trend axis and the CO bar. */
export const CO_SCALE: Scale = { euMin: 0, euMax: 100, unit: '%' };

/**
 * CO display scale. The range stays the fixed 0–100 valve percentage — only the
 * unit is per-loop today; honouring `out_scale.eu_*` is a separate change that
 * has to move the CO entry box and the trend's right axis with it.
 */
export function coScale(controller: ControllerResponse): Scale {
  return { euMin: 0, euMax: 100, unit: controller.out_scale?.unit || '%' };
}
