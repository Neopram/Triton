import Link from "next/link";
import { useRouter } from "next/router";
import { ReactNode } from "react";
import { useAuthStore } from "@/store/authStore";
import clsx from "clsx";
import {
  Home,
  Ship,
  FileText,
  DollarSign,
  Globe,
  Brain,
  Leaf,
  LogOut,
  Book,
} from "lucide-react";

const menu = [
  { name: "Dashboard", path: "/dashboard", icon: <Home size={18} /> },
  { name: "Voyage Planner", path: "/modules/voyage", icon: <Ship size={18} /> },
  { name: "Fleet Tracker", path: "/modules/fleet", icon: <Globe size={18} /> },
  { name: "Finance", path: "/modules/finance", icon: <DollarSign size={18} /> },
  { name: "OCR", path: "/modules/ocr", icon: <FileText size={18} /> },
  { name: "Market", path: "/modules/market", icon: <Globe size={18} /> },
  { name: "AI Command", path: "/modules/ai", icon: <Brain size={18} /> },
  { name: "Emissions", path: "/modules/emissions", icon: <Leaf size={18} /> },
  { name: "Knowledge Base", path: "/knowledge", icon: <Book size={18} />, badge: "New" }, // Nuevo elemento
];

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const router = useRouter();
  const { logout, user } = useAuthStore();

  return (
    <div className="flex min-h-screen bg-gray-100">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r shadow-sm hidden md:flex flex-col">
        <div className="h-16 flex items-center justify-center border-b text-xl font-bold text-blue-700">
          Maritime AI
        </div>
        <nav className="flex-1 px-4 py-6 space-y-2">
          {menu.map((item) => (
            <Link href={item.path} key={item.name}>
              <div
                className={clsx(
                  "flex items-center space-x-2 p-3 rounded-lg cursor-pointer text-sm font-medium transition",
                  router.pathname === item.path
                    ? "bg-blue-100 text-blue-700 font-semibold"
                    : "hover:bg-gray-100 text-gray-700"
                )}
              >
                {item.icon}
                <span>{item.name}</span>
                {item.badge && (
                  <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-700">
                    {item.badge}
                  </span>
                )}
              </div>
            </Link>
          ))}
        </nav>
        <div className="p-4 border-t text-sm text-gray-600">
          <p className="mb-2">
            Logged in as <strong>{user?.username}</strong> ({user?.role})
          </p>
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="text-red-600 hover:underline"
          >
            <LogOut size={14} className="inline mr-1" />
            Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col">
        <header className="bg-white h-16 px-6 border-b flex items-center justify-between shadow-sm">
          <h1 className="text-lg font-semibold text-gray-800">Maritime Business Intelligence</h1>
        </header>
        <section className="p-6 flex-1 overflow-y-auto">{children}</section>
      </main>
    </div>
  );
}