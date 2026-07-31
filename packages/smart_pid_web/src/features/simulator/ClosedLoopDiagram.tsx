import { cn } from '@/lib/utils';
import { PID_MODE_AUTO, type ControllerSimStatus } from './types';

export interface ClosedLoopDiagramProps {
  /** Undefined for a restricted operator — the diagram still shows the generic topology. */
  controller?: ControllerSimStatus | null;
}

const ARROW_MARKER_ID = 'closed-loop-arrow';

/** Matches DynamicsSliders' 2-decimal readout convention — also keeps every
 * label short enough to stay inside its block, since raw floats (random-walk
 * auto-excitation, unrounded backend values) can run to 15+ digits. */
function fmt(n: number): string {
  return n.toFixed(2);
}

/**
 * Illustrative SP → PID → CO → Processo → PV block diagram of the simulated
 * loop, with the feedback path and disturbance injection that make it
 * visibly closed. Purely presentational — reads the same status snapshot the
 * control panel already fetches, never triggers its own request.
 */
export function ClosedLoopDiagram({ controller }: ClosedLoopDiagramProps) {
  const disturbed = controller?.step_active === true || controller?.noise_active === true;
  const pidEnabled = controller?.pid_enabled === true;
  const pidAuto = controller?.pid_mode === PID_MODE_AUTO;

  return (
    <figure className="flex flex-col gap-2 rounded-control border border-rule bg-surface p-3">
      <figcaption className="text-2xs font-medium uppercase tracking-wider text-text-soft">
        Malha de controle simulada
      </figcaption>
      <svg
        role="img"
        aria-label="Diagrama da malha de controle"
        viewBox="0 0 640 205"
        className="h-auto w-full"
      >
        <defs>
          <marker
            id={ARROW_MARKER_ID}
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M0 0 L10 5 L0 10 z" className="fill-rule-strong" />
          </marker>
        </defs>

        {/* SP input */}
        <g>
          <title>Setpoint — valor desejado para a variável de processo.</title>
          <text x="10" y="72" className="fill-trace-sp text-xs font-semibold">
            SP
          </text>
          {controller ? (
            <text x="10" y="90" className="fill-trace-sp text-[9px]">
              {fmt(controller.sp)}
            </text>
          ) : null}
        </g>
        <line
          x1="40"
          y1="80"
          x2="70"
          y2="80"
          className="stroke-rule-strong"
          strokeWidth="1.5"
          markerEnd={`url(#${ARROW_MARKER_ID})`}
        />

        {/* Summing junction */}
        <g>
          <title>Junção somadora — calcula o erro (SP − PV) que alimenta o PID.</title>
          <circle cx="86" cy="80" r="16" className="fill-surface-sunk stroke-rule-strong" strokeWidth="1.5" />
          <text x="86" y="85" textAnchor="middle" className="fill-text text-sm">
            Σ
          </text>
        </g>
        <line
          x1="102"
          y1="80"
          x2="150"
          y2="80"
          className="stroke-rule-strong"
          strokeWidth="1.5"
          markerEnd={`url(#${ARROW_MARKER_ID})`}
        />
        {/* Erro (SP − PV) on the junction output */}
        <g>
          <title>Erro (SP − PV) que o PID tenta zerar.</title>
          <text x="126" y="70" textAnchor="middle" className="fill-text-soft text-2xs font-semibold">
            ERRO
          </text>
          {controller ? (
            <text x="126" y="92" textAnchor="middle" className="fill-text-soft text-[9px]">
              {fmt(controller.error)}
            </text>
          ) : null}
        </g>

        {/* PID block */}
        <g className={cn(controller != null && !pidEnabled && 'opacity-40')}>
          <title>
            Controlador PID interno do gêmeo digital — soma o erro (SP - PV) ponderado por Kp,
            Ti, Td e escreve em CO quando habilitado e em AUTO.
          </title>
          <rect
            x="150"
            y="50"
            width="140"
            height="60"
            rx="6"
            className="fill-surface-sunk stroke-rule-strong"
            strokeWidth="1.5"
          />
          <text x="220" y="68" textAnchor="middle" className="fill-text text-sm font-semibold">
            PID
          </text>
          {controller ? (
            <>
              <text x="220" y="84" textAnchor="middle" className="fill-text-soft text-[9px]">
                {`Kp ${fmt(controller.pid_kp)} · Ti ${fmt(controller.pid_ti)} · Td ${fmt(controller.pid_td)}`}
              </text>
              <text x="220" y="98" textAnchor="middle" className="fill-text-soft text-[9px] uppercase">
                {pidAuto ? 'AUTO' : 'MAN'}
              </text>
            </>
          ) : null}
        </g>
        <line
          x1="290"
          y1="80"
          x2="330"
          y2="80"
          className="stroke-rule-strong"
          strokeWidth="1.5"
          markerEnd={`url(#${ARROW_MARKER_ID})`}
        />
        {/* CO on the PID output */}
        <g>
          <title>Saída de controle (CO) escrita pelo PID.</title>
          <text x="310" y="70" textAnchor="middle" className="fill-trace-co text-2xs font-semibold">
            CO
          </text>
          {controller ? (
            <text x="310" y="92" textAnchor="middle" className="fill-trace-co text-[9px]">
              {fmt(controller.co)}
            </text>
          ) : null}
        </g>

        {/* Processo block */}
        <g>
          <title>
            Processo simulado — planta de primeira/segunda ordem com atraso de transporte,
            transforma CO na resposta do processo segundo o ganho, as constantes de tempo e o
            tempo morto.
          </title>
          <rect
            x="330"
            y="50"
            width="140"
            height="60"
            rx="6"
            className="fill-surface-sunk stroke-rule-strong"
            strokeWidth="1.5"
          />
          <text x="400" y="68" textAnchor="middle" className="fill-text text-sm font-semibold">
            Processo
          </text>
          {controller ? (
            <>
              <text x="400" y="82" textAnchor="middle" className="fill-text-soft text-[9px]">
                {`Ganho ${fmt(controller.gain)} · τ1 ${fmt(controller.tau1)}`}
              </text>
              <text x="400" y="94" textAnchor="middle" className="fill-text-soft text-[9px]">
                {controller.tau2
                  ? `τ2 ${fmt(controller.tau2)} · L ${fmt(controller.dead_time)}`
                  : `L ${fmt(controller.dead_time)}`}
              </text>
            </>
          ) : null}
        </g>

        <line
          x1="470"
          y1="80"
          x2="490"
          y2="80"
          className="stroke-rule-strong"
          strokeWidth="1.5"
          markerEnd={`url(#${ARROW_MARKER_ID})`}
        />

        {/* Disturbance summing junction — pv = process_output + disturbance */}
        <g>
          <title>
            Somador de perturbação — soma a resposta do processo à perturbação (degrau ou ruído)
            para formar o PV.
          </title>
          <circle
            cx="506"
            cy="80"
            r="16"
            className={cn('fill-surface-sunk stroke-rule-strong', disturbed && 'stroke-alarm-adv')}
            strokeWidth="1.5"
          />
          <text x="506" y="85" textAnchor="middle" className="fill-text text-sm">
            +
          </text>
        </g>
        <line
          x1="506"
          y1="10"
          x2="506"
          y2="64"
          className={cn(disturbed ? 'stroke-alarm-adv' : 'stroke-rule-strong')}
          strokeWidth="1.5"
          markerEnd={`url(#${ARROW_MARKER_ID})`}
        />
        <text
          x="506"
          y="8"
          textAnchor="middle"
          className={cn('text-2xs font-semibold', disturbed ? 'fill-alarm-adv' : 'fill-text-soft')}
        >
          Perturbação
        </text>
        {controller ? (
          <text
            x="514"
            y="44"
            className={cn('text-[9px]', disturbed ? 'fill-alarm-adv' : 'fill-text-soft')}
          >
            {fmt(controller.disturbance_output)}
          </text>
        ) : null}

        {/* PV out */}
        <line
          x1="522"
          y1="80"
          x2="560"
          y2="80"
          className="stroke-rule-strong"
          strokeWidth="1.5"
          markerEnd={`url(#${ARROW_MARKER_ID})`}
        />
        <g>
          <title>Variável de processo (PV) medida, realimentada na junção somadora.</title>
          <text x="524" y="72" className="fill-trace-pv text-2xs font-semibold">
            PV
          </text>
          {controller ? (
            <text x="524" y="90" className="fill-trace-pv text-[9px]">
              {fmt(controller.pv)}
            </text>
          ) : null}
        </g>

        {/* Feedback path, routed below the main flow back into the junction. */}
        <path
          d="M 560 80 L 582 80 L 582 178 L 86 178 L 86 96"
          fill="none"
          className="stroke-rule-strong"
          strokeWidth="1.5"
          strokeDasharray="4 3"
          markerEnd={`url(#${ARROW_MARKER_ID})`}
        />
        <text x="330" y="193" textAnchor="middle" className="fill-text-soft text-2xs">
          realimentação
        </text>
      </svg>
    </figure>
  );
}
