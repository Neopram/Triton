import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import useAuthStore from "@/store/authStore";
import api from "@/services/api";
import { Ship, DollarSign, Leaf, MapPin, BarChart4 } from "lucide-react";
import Chart from "@/components/Chart";
import Button from "@/components/Button";
import Link from "next/link";
import AdminPanel from '@/modules/Admin';

const modules = [
  { title: "Voyage Calculator", href: "/modules/voyage", description: "Optimize TCE, freight, delays, and routing." },
  { title: "Fleet Tracker", href: "/modules/fleet", description: "Live AIS tracking and port ETA projections." },
  { title: "PnL & Finance", href: "/modules/finance", description: "Track profitability per vessel, voyage or route." },
  { title: "Market Intelligence", href: "/modules/market", description: "Upload and analyze market reports and trends." },
  { title: "Market Analysis", href: "/modules/market/analysis", description: "AI-driven insights from uploaded freight market data." },
  { title: "OCR Documents", href: "/modules/ocr", description: "Scan and structure bills, reports, and invoices." },
  { title: "AI Command", href: "/modules/ai", description: "Ask strategic or operational questions to DeepSeek." },
  { title: "ESG Emissions", href: "/modules/emissions", description: "Monitor EEXI, CII, and CO₂ per trip or fleet." }
];

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuthStore();

  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const res = await api.get("/finance/dashboard-summary");
        setSummary(res.data);
      } catch (err) {
        console.error("Failed to load summary:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 text-gray-800">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 bg-white shadow-md">
        <div>
          <h1 className="text-2xl font-bold text-blue-700">Maritime Intelligence Dashboard</h1>
          <p className="text-sm text-gray-500">Welcome, {user?.username} ({user?.role})</p>
        </div>
        <button
          onClick={() => {
            logout();
            router.push("/login");
          }}
          className="text-sm bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
        >
          Logout
        </button>
      </header>

      {/* Admin Panel (only for admin users) */}
      {user?.role === 'admin' && (
        <div className="px-6 mt-8">
          <AdminPanel />
        </div>
      )}

      {/* KPIs */}
      <main className="p-6 space-y-8">
        {!loading && summary && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <StatCard
                icon={<Ship size={20} />}
                label="Active Vessels"
                value={summary.vessels_active ?? "—"}
              />
              <StatCard
                icon={<DollarSign size={20} />}
                label="Avg TCE"
                value={`$${summary.avg_tce ?? "—"}`}
              />
              <StatCard
                icon={<Leaf size={20} />}
                label="CO₂ This Month"
                value={`${summary.co2_emissions ?? "—"} MT`}
              />
              <StatCard
                icon={<MapPin size={20} />}
                label="Active Routes"
                value={summary.routes_active ?? "—"}
              />
            </div>

            <div className="bg-white p-6 rounded-xl shadow border">
              <Chart
                type="line"
                title="Monthly PnL Overview"
                data={summary.monthly_pnl ?? []}
                dataKeyX="month"
                dataKeysY={["pnl"]}
              />
            </div>
          </>
        )}

        {/* Navigation Tiles */}
        <div className="grid gap-6 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
          {modules.map((mod) => (
            <div
              key={mod.title}
              onClick={() => router.push(mod.href)}
              className="cursor-pointer bg-white border rounded-2xl shadow hover:shadow-lg transition p-5"
            >
              <h2 className="text-lg font-semibold text-blue-800 mb-2">{mod.title}</h2>
              <p className="text-sm text-gray-600">{mod.description}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: JSX.Element;
  label: string;
  value: string | number;
}) {
  return (
    <div className="bg-white p-4 rounded-xl border shadow-sm flex items-center space-x-4">
      <div className="p-2 bg-blue-100 rounded-lg text-blue-700">{icon}</div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-lg font-bold text-gray-900">{value}</p>
      </div>
    </div>
  );
}