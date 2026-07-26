import { AlarmPanel } from '@/features/alarms/AlarmPanel';
import { AlarmFooterBar } from '@/features/dashboard/AlarmFooterBar';

/**
 * Alarm workspace (§6.4). The persistent §6.9 footer stays mounted here too —
 * it is the plant-wide summary, so navigating INTO the alarm page must not be
 * the one place an operator loses it.
 */
export function AlarmsPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <AlarmPanel />
      <AlarmFooterBar />
    </div>
  );
}
