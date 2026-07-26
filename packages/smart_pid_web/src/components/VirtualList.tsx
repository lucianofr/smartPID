import { useRef, type Key, type ReactNode } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { cn } from '@/lib/utils';

export interface VirtualListProps<T> {
  items: readonly T[];
  renderItem: (item: T, index: number) => ReactNode;
  /** Scroll viewport height (px number or any CSS size). */
  height: number | string;
  /** Estimated row height in px (fixed-size windowing). */
  estimateSize?: number;
  overscan?: number;
  getKey?: (item: T, index: number) => Key;
  role?: string;
  'aria-label'?: string;
  className?: string;
}

/** Windowed list for floods (§7: alarm flood). Fixed-size rows, no measurement. */
export function VirtualList<T>({
  items,
  renderItem,
  height,
  estimateSize = 40,
  overscan = 8,
  getKey,
  role = 'list',
  'aria-label': ariaLabel,
  className,
}: VirtualListProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateSize,
    overscan,
  });

  return (
    <div
      ref={parentRef}
      role={role}
      aria-label={ariaLabel}
      className={cn('overflow-y-auto', className)}
      style={{ height }}
    >
      <div className="relative w-full" style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((v) => (
          <div
            key={getKey ? getKey(items[v.index], v.index) : v.key}
            role={role === 'list' ? 'listitem' : undefined}
            data-index={v.index}
            className="absolute left-0 top-0 w-full"
            style={{ height: `${v.size}px`, transform: `translateY(${v.start}px)` }}
          >
            {renderItem(items[v.index], v.index)}
          </div>
        ))}
      </div>
    </div>
  );
}