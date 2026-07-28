import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { statusTimestampToEpoch, type StatusData } from '@/lib/envelope';
import { createWindowBuffer, type WindowBuffer } from '@/lib/windowBuffer';
import { useRealtime } from '@/realtime/useRealtime';
import {
  freeSlot,
  MAX_SLOTS,
  SIGNALS,
  type AlignedSeries,
  type Signal,
  type SignalKey,
  type TrendSlot,
} from './types';
import { readTrendSelection, writeTrendSelection } from './trendSelectionStore';

/**
 * The four-slot multi-trend model (§6.8).
 *
 * Each occupied slot owns ONE loop and ONE `WindowBuffer`, so every line in a
 * slot shares that buffer's time column. That kills by construction the
 * cross-loop misalignment the deleted client had to patch (uPlot indexes every
 * series by position, so two loops buffered at different times plotted the
 * younger row against the older timestamps).
 *
 * Buffers accumulate only for loops that currently occupy a slot: an operator
 * watching two loops must not pay for the other thirty.
 */

/** Design-system §7.2 sliding window: ~600 points over ~60 s. */
export const LIVE_WINDOW_SECONDS = 60;
export const LIVE_MAX_POINTS = 600;

const BUFFERED_SIGNALS = 3; // pv, sp, co — always buffered, drawn on demand.
const SLOT_RANGE_ERROR = `slot must be between 0 and ${MAX_SLOTS - 1}`;

const EMPTY_SERIES: AlignedSeries = { keys: [], data: [[]] };

function assertSlot(slot: number): void {
  if (!Number.isInteger(slot) || slot < 0 || slot >= MAX_SLOTS) {
    throw new RangeError(SLOT_RANGE_ERROR);
  }
}

export interface MultiTrendModel {
  slots: readonly TrendSlot[];
  /** Flat line list, ordered by slot then pv/sp/co. */
  selection: readonly SignalKey[];
  /** Per-slot uPlot columns; index matches `slots`, free slots yield no keys. */
  slotSeries: readonly AlignedSeries[];
  /** Every slot taken — a further controller cannot be plotted. */
  isFull: boolean;
  paused: boolean;
  /** Put a controller in a slot with all three signals on (§6.8 default). */
  assign(slot: number, controller: { id: number }): void;
  /** Release a slot and drop its buffer. */
  clear(slot: number): void;
  toggleSeries(slot: number, signal: Signal): void;
  /** Checkbox-grid bridge: flip one (loop, signal) without naming a slot. */
  toggleSignal(loopId: number, signal: Signal): void;
  isSelected(loopId: number, signal: Signal): boolean;
  setPaused(paused: boolean): void;
  /** Chart width in CSS px — drives min/max decimation. */
  setPxWidth(px: number): void;
}

export function useMultiTrendModel(roster: readonly number[] | null): MultiTrendModel {
  // Lazily initialised from storage: a layout an operator built must survive a
  // navigation, a reload and a browser restart (§9.1).
  const [slots, setSlots] = useState<TrendSlot[]>(readTrendSelection);
  const [paused, setPaused] = useState(false);
  const [pxWidth, setPxWidth] = useState(800);
  const [revision, setRevision] = useState(0);

  const buffers = useRef(new Map<number, WindowBuffer>());
  // The subscription is registered once (the relay identity is stable); slot
  // and pause state are read through refs so a selection change never drops a frame.
  const slotsRef = useRef(slots);
  slotsRef.current = slots;
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  const { subscribe } = useRealtime<StatusData>(null, 'status');

  useEffect(
    () =>
      subscribe((env) => {
        if (pausedRef.current) return;
        const loopId = env.loop_id;
        if (loopId === null) return;
        if (!slotsRef.current.some((s) => s.controllerId === loopId)) return;
        const t = statusTimestampToEpoch(env.data.timestamp) ?? env.ts;
        let buffer = buffers.current.get(loopId);
        if (buffer === undefined) {
          buffer = createWindowBuffer(BUFFERED_SIGNALS, {
            maxSeconds: LIVE_WINDOW_SECONDS,
            maxPoints: LIVE_MAX_POINTS,
          });
          buffers.current.set(loopId, buffer);
        }
        // push() rejects a repeated or out-of-order t — that is the de-dupe for
        // coalesced frames, so only a real sample bumps the revision.
        if (buffer.push(t, [env.data.pv.value, env.data.sp.value, env.data.co.value])) {
          setRevision((r) => r + 1);
        }
      }),
    [subscribe],
  );

  useEffect(() => {
    writeTrendSelection(slots);
  }, [slots]);

  /**
   * One-shot reconciliation against the live roster (§9.2). A restored slot for
   * a loop that no longer exists would render a permanently empty cell, and a
   * slot with no signal left is not a selection. Gated on `roster !== null`: an
   * unresolved query must never be read as "every loop is gone".
   */
  const reconciled = useRef(false);
  useEffect(() => {
    if (roster === null || reconciled.current) return;
    reconciled.current = true;
    setSlots((prev) =>
      prev.map((s) => {
        if (s.controllerId === null) return s;
        const silent = !s.series.pv && !s.series.sp && !s.series.co;
        if (!roster.includes(s.controllerId) || silent) {
          buffers.current.delete(s.controllerId);
          return freeSlot();
        }
        return s;
      }),
    );
  }, [roster]);

  const assign = useCallback((slot: number, controller: { id: number }) => {
    assertSlot(slot);
    setSlots((prev) => {
      const evicted = prev[slot].controllerId;
      if (evicted !== null && evicted !== controller.id) buffers.current.delete(evicted);
      return prev.map((s, i) => {
        if (i === slot) {
          return { controllerId: controller.id, series: { pv: true, sp: true, co: true } };
        }
        // A controller lives in at most one cell.
        return s.controllerId === controller.id ? freeSlot() : s;
      });
    });
  }, []);

  const clear = useCallback((slot: number) => {
    assertSlot(slot);
    setSlots((prev) => {
      const held = prev[slot].controllerId;
      if (held !== null) buffers.current.delete(held);
      return prev.map((s, i) => (i === slot ? freeSlot() : s));
    });
  }, []);

  const toggleSeries = useCallback((slot: number, signal: Signal) => {
    assertSlot(slot);
    setSlots((prev) =>
      prev.map((s, i) => {
        if (i !== slot || s.controllerId === null) return s;
        const series = { ...s.series, [signal]: !s.series[signal] };
        if (!series.pv && !series.sp && !series.co) {
          buffers.current.delete(s.controllerId);
          return freeSlot();
        }
        return { ...s, series };
      }),
    );
  }, []);

  const toggleSignal = useCallback((loopId: number, signal: Signal) => {
    setSlots((prev) => {
      const held = prev.findIndex((s) => s.controllerId === loopId);
      if (held >= 0) {
        const series = { ...prev[held].series, [signal]: !prev[held].series[signal] };
        const empty = !series.pv && !series.sp && !series.co;
        if (empty) buffers.current.delete(loopId);
        return prev.map((s, i) => (i === held ? (empty ? freeSlot() : { ...s, series }) : s));
      }
      const free = prev.findIndex((s) => s.controllerId === null);
      if (free < 0) return prev; // grid full — the fifth loop is simply not addable
      return prev.map((s, i) =>
        i === free
          ? { controllerId: loopId, series: { pv: false, sp: false, co: false, [signal]: true } }
          : s,
      );
    });
  }, []);

  const isSelected = useCallback(
    (loopId: number, signal: Signal) =>
      slots.some((s) => s.controllerId === loopId && s.series[signal]),
    [slots],
  );

  const selection = useMemo<SignalKey[]>(
    () =>
      slots.flatMap(({ controllerId, series }) =>
        controllerId === null
          ? []
          : SIGNALS.filter((s) => series[s]).map((signal) => ({ loopId: controllerId, signal })),
      ),
    [slots],
  );

  const slotSeries = useMemo<AlignedSeries[]>(
    () =>
      slots.map(({ controllerId, series }) => {
        if (controllerId === null) return EMPTY_SERIES;
        const signals = SIGNALS.filter((s) => series[s]);
        const keys = signals.map((signal) => ({ loopId: controllerId, signal }));
        const buffer = buffers.current.get(controllerId);
        if (buffer === undefined) return { keys, data: [[], ...signals.map(() => [])] };
        // One buffer per slot: min/max decimation happens on already-aligned
        // columns, so every drawn row keeps the shared time axis.
        const [t, ...rows] = buffer.view(pxWidth).data;
        return { keys, data: [t, ...signals.map((signal) => rows[SIGNALS.indexOf(signal)])] };
      }),
    // `revision` is the in-place mutation signal for the buffer map.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [slots, pxWidth, revision],
  );

  const isFull = slots.every((s) => s.controllerId !== null);

  return {
    slots,
    selection,
    slotSeries,
    isFull,
    paused,
    assign,
    clear,
    toggleSeries,
    toggleSignal,
    isSelected,
    setPaused,
    setPxWidth,
  };
}
