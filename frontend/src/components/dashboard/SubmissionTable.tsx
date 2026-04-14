import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { StatusBadge } from '../ui/StatusBadge'
import type { SubmissionListItem } from '../../lib/types'
import { PROVIDER_TYPE_LABELS, ENTITY_TYPE_LABELS } from '../../lib/types'

interface SubmissionTableProps {
  items: SubmissionListItem[]
  total: number
  page: number
  size: number
  onPageChange: (page: number) => void
}

function formatDate(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function SubmissionTable({
  items,
  total,
  page,
  size,
  onPageChange,
}: SubmissionTableProps) {
  const { t } = useTranslation()
  const totalPages = Math.ceil(total / size)
  const hasPrev = page > 1
  const hasNext = page < totalPages

  const start = (page - 1) * size + 1
  const end = Math.min(page * size, total)

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {[
                t('submission.table.date'),
                t('submission.table.provider'),
                t('submission.table.type'),
                t('submission.table.entity'),
                t('submission.table.country'),
                t('submission.table.status'),
                'Action',
              ].map((col) => (
                <th
                  key={col}
                  scope="col"
                  className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-gray-100 bg-white">
            {items.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-12 text-center text-sm text-gray-500"
                >
                  {t('dashboard.noSubmissions')}
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                    {formatDate(item.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-sm font-medium text-gray-900">
                      {item.provider_name}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                    {PROVIDER_TYPE_LABELS[item.provider_type]}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                    {ENTITY_TYPE_LABELS[item.entity_type]}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {item.country}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <Link
                      to={`/submissions/${item.id}`}
                      className="inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-800 transition-colors"
                    >
                      View
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > size && (
        <div className="flex items-center justify-between border-t border-gray-200 bg-gray-50 px-4 py-3">
          <p className="text-sm text-gray-600">
            {t('submission.pagination.showing')}{' '}
            <span className="font-medium">{start}</span>–
            <span className="font-medium">{end}</span>{' '}
            {t('submission.pagination.of')}{' '}
            <span className="font-medium">{total}</span>{' '}
            {t('submission.pagination.results')}
          </p>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={!hasPrev}
              aria-label={t('submission.pagination.previous')}
              className="p-1.5 rounded-md border border-gray-300 bg-white text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-sm text-gray-700">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={!hasNext}
              aria-label={t('submission.pagination.next')}
              className="p-1.5 rounded-md border border-gray-300 bg-white text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
