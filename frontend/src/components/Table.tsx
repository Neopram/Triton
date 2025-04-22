import React from "react";
import clsx from "clsx";

interface TableProps {
  columns: string[];
  data: Array<Record<string, any>>;
  rowKey?: string;
  className?: string;
  emptyMessage?: string;
}

export default function Table({
  columns,
  data,
  rowKey = "id",
  className = "",
  emptyMessage = "No data available"
}: TableProps) {
  return (
    <div className={clsx("overflow-x-auto rounded-lg shadow-sm border", className)}>
      <table className="min-w-full text-sm text-left text-gray-800">
        <thead className="bg-gray-100 sticky top-0">
          <tr>
            {columns.map((col) => (
              <th key={col} className="px-4 py-3 font-semibold whitespace-nowrap border-b text-gray-600">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="text-center py-8 text-gray-500 italic">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, idx) => (
              <tr
                key={row[rowKey] ?? idx}
                className="hover:bg-gray-50 border-t transition duration-150"
              >
                {columns.map((col) => (
                  <td key={col} className="px-4 py-3 whitespace-nowrap border-b">
                    {row[col] !== undefined ? row[col] : "-"}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
