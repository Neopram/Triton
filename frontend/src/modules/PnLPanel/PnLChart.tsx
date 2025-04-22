import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip } from "recharts";

interface ChartData {
  month: string;
  profit_usd: number;
}

interface PnLChartProps {
  data: ChartData[];
}

export default function PnLChart({ data }: PnLChartProps) {
  return (
    <div className="bg-white p-6 rounded-xl shadow border">
      <h3 className="text-xl font-semibold text-blue-700 mb-4">📈 Monthly Net Profit</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis />
          <Tooltip formatter={(value: any) => `$${Number(value).toFixed(2)}`} />
          <Line type="monotone" dataKey="profit_usd" stroke="#1D4ED8" strokeWidth={3} dot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
