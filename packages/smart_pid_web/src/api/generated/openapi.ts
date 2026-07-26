/**
 * Hand-crafted openapi-typescript fixture.
 *
 * The real codegen pipeline is `npm run gen:api` (openapi-typescript 7 against
 * the running backend at /openapi.json); see docs/superpowers/plans/phase2.
 * This file ships only the six schemas phase 3 consumes from
 * `components['schemas']` so the new client can compile without a live
 * backend. Regenerate via `npm run gen:api` to replace it with the full
 * openapi-typescript output; this stub is meant to be overwritten in place.
 */
export interface paths {}

export interface components {
  schemas: {
    LoginRequest: {
      username: string;
      password: string;
    };
    TokenResponse: {
      access_token: string;
      token_type: string;
    };
    UserClaims: {
      user_id: number;
      username: string;
      role: 'admin' | 'user';
    };
    ControllerResponse: {
      id: number;
      name: string;
      description: string;
      mode: string;
      pv: number;
      sp: number;
      co: number;
      execution_mode: string;
      scan_rate_s: number;
      tss_s: number;
      process_speed: string;
      pid_params: {
        kp: number;
        ti: number;
        td: number;
      };
      pid_structure: string;
      integral_type: string;
      pv_scale: {
        eu_min: number;
        eu_max: number;
        unit: string;
        raw_min: number;
        raw_max: number;
        clamping_enabled: boolean;
      };
      out_scale: {
        eu_min: number;
        eu_max: number;
        unit: string;
        raw_min: number;
        raw_max: number;
        clamping_enabled: boolean;
      };
      tag_bindings: {
        pv_node_id: string | null;
        sp_node_id: string | null;
        co_node_id: string | null;
        bkcal_in_node_id: string | null;
        bkcal_out_node_id: string | null;
      };
      control_opts: {
        anti_windup: string;
        derivative_filter_s: number;
        setpoint_ramp_s: number;
        output_slew_s: number;
      };
      io_opts: {
        reverse_actuating: boolean;
        output_clamping: boolean;
        bkcal_handling: string;
        shed_opt: string | null;
        shed_time_s: number | null;
      };
      ai_config: {
        enabled: boolean;
        engine: string;
        objective: string;
        speed: string;
      };
      optimization_enabled: boolean;
      tuning_write_mode: string;
      max_tuning_change_pct: number;
      process_input_node_id: string | null;
      process_output_node_id: string | null;
      disturbance_node_id: string | null;
      shed_opt: string | null;
      shed_time_s: number | null;
    };
    AIStatusResponse: {
      controller_id: number;
      engine: string;
      objective: string;
      speed: string;
      current_ki: number;
      last_gamma: number | null;
      enabled: boolean;
    };
    OPCUAStatusResponse: {
      state: string;
      endpoint: string;
    };
    SimulatorStatusResponse: {
      enabled: boolean;
      running: boolean;
      controllers: Record<
        number,
        {
          preset: string;
          parameters: Record<string, number>;
          disturbance: unknown;
          auto_sp: unknown;
          auto_disturbance: unknown;
          pv: number;
          sp: number;
          co: number;
          error: number;
          process_input: number;
          process_output: number;
          disturbance_output: number;
        }
      >;
    };
  };
}

export interface operations {}