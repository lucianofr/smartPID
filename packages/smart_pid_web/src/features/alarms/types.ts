export type AlarmType = 'HIHI' | 'HI' | 'LO' | 'LOLO' | 'DV_HI' | 'DV_LO';
export type AlarmPriority = 'CRITICAL' | 'WARNING' | 'ADVISORY' | 'LOG';
export type AlarmStatus = 'UNACKNOWLEDGED' | 'ACKNOWLEDGED' | 'CLEARED_UNACK';

/** One row from GET /alarms/active (bare dict — typed here by hand, see Task 0.2). */
export interface ActiveAlarm {
  id: number;
  controller_id: number;
  controller_name: string;
  alarm_type: AlarmType;
  priority: AlarmPriority;
  value: number;
  limit: number;
  timestamp: string; // ISO UTC
  cleared_at: string | null;
  acknowledged: number; // 0 | 1
  ack_by_user: string | null;
  ack_at: string | null;
  status: AlarmStatus;
}

export interface AlarmThreshold {
  alarm_type: AlarmType;
  priority: AlarmPriority; // backend default "WARNING"
  limit: number; // default 0.0
  enabled: boolean; // default true
  deadband: number; // default 0.0
  delay_on_s: number; // default 0.0
  delay_off_s: number; // default 0.0
}

export interface AlarmConfigResponse {
  controller_id: number;
  thresholds: AlarmThreshold[];
}

export interface AlarmConfigUpdate {
  thresholds: AlarmThreshold[];
}
