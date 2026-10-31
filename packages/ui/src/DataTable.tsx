import type { ReactNode } from 'react';

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  caption: string;
  emptyMessage: string;
}

// Accessible table with a caption and scope-labelled headers.
export function DataTable<T>({ columns, rows, rowKey, caption, emptyMessage }: DataTableProps<T>) {
  if (rows.length === 0) {
    return <p className="py-4 text-slate-600">{emptyMessage}</p>;
  }
  return (
    <table className="w-full border-collapse text-left text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b border-slate-300">
          {columns.map((col) => (
            <th key={col.key} scope="col" className="px-3 py-2 font-semibold text-slate-700">
              {col.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={rowKey(row)} className="border-b border-slate-100">
            {columns.map((col) => (
              <td key={col.key} className="px-3 py-2 align-top">
                {col.render(row)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
