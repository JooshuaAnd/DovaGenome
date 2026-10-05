import type { ReactNode } from 'react'

import { EmptyState } from '@/components/common/EmptyState'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'

/**
 * Column definition for {@link DataTable}.
 *
 * Keeping column metadata declarative lets later tasks add sorting and filtering
 * without rewriting every call site.
 */
export interface DataTableColumn<TRow> {
  /** Stable key; also used as the accessible header id. */
  id: string
  header: ReactNode
  /** Cell renderer. Receives the row and its index. */
  cell: (row: TRow, index: number) => ReactNode
  /** Tailwind width hint, e.g. `w-40`. */
  className?: string
  /** Hide on small screens to keep tables readable on mobile. */
  hideBelow?: 'sm' | 'md' | 'lg' | 'xl'
  /** Right-align numeric cells and their header. */
  align?: 'left' | 'right'
}

const HIDE_CLASS: Record<NonNullable<DataTableColumn<unknown>['hideBelow']>, string> = {
  sm: 'hidden sm:table-cell',
  md: 'hidden md:table-cell',
  lg: 'hidden lg:table-cell',
  xl: 'hidden xl:table-cell',
}

export interface DataTableProps<TRow> {
  columns: DataTableColumn<TRow>[]
  rows: TRow[]
  rowKey: (row: TRow, index: number) => string
  /** Row click handler; omit for static tables. */
  onRowClick?: (row: TRow) => void
  loading?: boolean
  /** Message shown when `rows` is empty. */
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: ReactNode
  /** Total count for the caption. */
  caption?: ReactNode
  className?: string
}

/**
 * Thin composition layer over the shadcn table that applies the product's
 * header treatment (uppercase micro-label on a warm tint) and handles the
 * empty state, so no page reimplements table chrome.
 */
export function DataTable<TRow>({
  columns,
  rows,
  rowKey,
  onRowClick,
  loading = false,
  emptyTitle = 'Belum ada data',
  emptyDescription,
  emptyAction,
  caption,
  className,
}: DataTableProps<TRow>) {
  if (!loading && rows.length === 0) {
    return (
      <EmptyState
        title={emptyTitle}
        description={emptyDescription}
        action={emptyAction}
        className={className}
      />
    )
  }

  return (
    <div className={cn('surface-card overflow-hidden', className)}>
      <Table>
        <TableHeader>
          <TableRow className="border-b border-line bg-cream hover:bg-cream">
            {columns.map((column) => (
              <TableHead
                key={column.id}
                className={cn(
                  'h-10 rounded-none px-4 text-[0.6875rem] font-extrabold tracking-[0.12em] text-muted-text uppercase',
                  column.align === 'right' && 'text-right',
                  column.className,
                  column.hideBelow && HIDE_CLASS[column.hideBelow],
                )}
              >
                {column.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>

        <TableBody>
          {rows.map((row, index) => (
            <TableRow
              key={rowKey(row, index)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cn('border-line', onRowClick && 'cursor-pointer')}
            >
              {columns.map((column) => (
                <TableCell
                  key={column.id}
                  className={cn(
                    'px-4 py-3 whitespace-normal text-ink-soft',
                    column.align === 'right' && 'text-right',
                    column.className,
                    column.hideBelow && HIDE_CLASS[column.hideBelow],
                  )}
                >
                  {column.cell(row, index)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {caption && (
        <p className="border-t border-line px-4 py-2.5 text-xs text-muted-text">{caption}</p>
      )}
    </div>
  )
}