import {
    ResponsiveContainer,
    LineChart,
    BarChart,
    AreaChart,
    Line,
    Bar,
    Area,
    CartesianGrid,
    XAxis,
    YAxis,
    Tooltip,
    Legend,
  } from "recharts";
  
  interface ChartProps {
    type: "line" | "bar" | "area";
    data: Array<Record<string, any>>;
    dataKeyX: string;
    dataKeysY: string[];
    colors?: string[];
    title?: string;
    height?: number;
  }
  
  export default function Chart({
    type = "line",
    data,
    dataKeyX,
    dataKeysY,
    colors = [],
    title,
    height = 300,
  }: ChartProps) {
    const ChartComponent =
      type === "line" ? LineChart : type === "bar" ? BarChart : AreaChart;
  
    return (
      <div className="bg-white p-4 shadow rounded-xl border">
        {title && (
          <h3 className="text-lg font-semibold text-blue-700 mb-3">{title}</h3>
        )}
        <ResponsiveContainer width="100%" height={height}>
          <ChartComponent data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={dataKeyX} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: "12px" }} />
  
            {dataKeysY.map((key, index) => {
              const color = colors[index] || `#${Math.floor(Math.random()*16777215).toString(16)}`;
              if (type === "line")
                return <Line key={key} type="monotone" dataKey={key} stroke={color} strokeWidth={2} dot={false} />;
              if (type === "bar")
                return <Bar key={key} dataKey={key} fill={color} />;
              if (type === "area")
                return <Area key={key} type="monotone" dataKey={key} stroke={color} fill={color} fillOpacity={0.3} />;
              return null;
            })}
          </ChartComponent>
        </ResponsiveContainer>
      </div>
    );
  }
  