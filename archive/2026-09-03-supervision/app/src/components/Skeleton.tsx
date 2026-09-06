/** Single shimmering placeholder block. */
export function Skeleton({ className = '' }: { className?: string }): JSX.Element {
  return <div className={`skeleton rounded-xl ${className}`} aria-hidden="true" />;
}

/** A stack of card-shaped skeletons for list/grid loading states. */
export function SkeletonList({ count = 4 }: { count?: number }): JSX.Element {
  return (
    <div className="grid gap-3" aria-busy="true" aria-live="polite">
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className="h-20 w-full" />
      ))}
    </div>
  );
}
