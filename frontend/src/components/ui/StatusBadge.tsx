import type { SubmissionStatus } from '../../lib/types'

interface StatusBadgeProps {
  status: SubmissionStatus
}

const CONFIG: Record<
  SubmissionStatus,
  { label: string; className: string }
> = {
  pending: {
    label: 'Processing',
    className: 'bg-amber-100 text-amber-700 border border-amber-200',
  },
  analysing: {
    label: 'Processing',
    className: 'bg-amber-100 text-amber-700 border border-amber-200',
  },
  complete: {
    label: 'Complete',
    className: 'bg-green-100 text-green-700 border border-green-200',
  },
  error: {
    label: 'Error',
    className: 'bg-red-100 text-red-700 border border-red-200',
  },
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const { label, className } = CONFIG[status]

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${className}`}
    >
      {(status === 'pending' || status === 'analysing') && (
        <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
      )}
      {label}
    </span>
  )
}
