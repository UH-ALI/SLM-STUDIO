import { classNames } from '@/lib/utils';

interface MetricRowProps {
  label: string;
  value: string | number;
  unit?: string;
  className?: string;
  labelClassName?: string;
  valueClassName?: string;
}

export function MetricRow({
  label,
  value,
  unit,
  className,
  labelClassName,
  valueClassName,
}: MetricRowProps) {
  const formattedValue =
    typeof value === 'number'
      ? value < 0.001
        ? value.toExponential(2)
        : value.toFixed(4)
      : value;

  return (
    <div
      className={classNames(
        'flex items-center justify-between py-2',
        className
      )}
    >
      <span
        className={classNames(
          'text-xs text-fern uppercase tracking-[0.06em]',
          labelClassName
        )}
      >
        {label}
      </span>
      <span
        className={classNames(
          'font-mono text-sm font-semibold text-gold tabular-nums',
          valueClassName
        )}
      >
        {formattedValue}
        {unit && <span className="text-muted ml-0.5">{unit}</span>}
      </span>
    </div>
  );
}
