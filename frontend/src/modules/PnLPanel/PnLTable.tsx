import Table from "@/components/Table";

interface PnLRecord {
  voyage_id: number;
  vessel_name: string;
  revenue_usd: number;
  total_costs_usd: number;
  profit_usd: number;
  pnl_margin_pct: number;
  comment?: string;
  created_at: string;
}

export default function PnLTable({ records }: { records: PnLRecord[] }) {
  return (
    <Table
      columns={[
        "Vessel",
        "Voyage ID",
        "Revenue (USD)",
        "Costs (USD)",
        "Profit (USD)",
        "Margin (%)",
        "Created At",
        "Notes"
      ]}
      data={records.map((rec, i) => ({
        id: i,
        Vessel: rec.vessel_name || `#${rec.voyage_id}`,
        "Voyage ID": rec.voyage_id,
        "Revenue (USD)": `$${rec.revenue_usd.toFixed(2)}`,
        "Costs (USD)": `$${rec.total_costs_usd.toFixed(2)}`,
        "Profit (USD)": `$${rec.profit_usd.toFixed(2)}`,
        "Margin (%)": `${rec.pnl_margin_pct.toFixed(2)}%`,
        "Created At": new Date(rec.created_at).toLocaleDateString(),
        Notes: rec.comment || "—",
      }))}
      emptyMessage="No financial records found."
    />
  );
}
