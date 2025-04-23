// Nuevo archivo: C:\Users\feder\Desktop\TritonAI\frontend\app\layout.tsx

import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import Link from "next/link"
import { 
  Home, Ship, FileText, DollarSign, 
  Globe, Brain, Leaf, Book
} from "lucide-react"

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Triton Maritime Intelligence',
  description: 'Advanced maritime intelligence platform powered by AI',
}

// Definir los elementos del menú
const menu = [
  { name: "Dashboard", path: "/dashboard", icon: <Home size={18} /> },
  { name: "Voyage Planner", path: "/modules/voyage", icon: <Ship size={18} /> },
  { name: "Fleet Tracker", path: "/modules/fleet", icon: <Globe size={18} /> },
  { name: "Finance", path: "/modules/finance", icon: <DollarSign size={18} /> },
  { name: "OCR", path: "/modules/ocr", icon: <FileText size={18} /> },
  { name: "Market", path: "/modules/market", icon: <Globe size={18} /> },
  { name: "AI Command", path: "/modules/ai", icon: <Brain size={18} /> },
  { name: "Emissions", path: "/modules/emissions", icon: <Leaf size={18} /> },
  { name: "Knowledge Base", path: "/knowledge", icon: <Book size={18} />, badge: "New" },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="flex min-h-screen bg-gray-100">
          {/* Sidebar */}
          <aside className="w-64 bg-white border-r shadow-sm hidden md:flex flex-col">
            <div className="h-16 flex items-center justify-center border-b text-xl font-bold text-blue-700">
              Triton Maritime AI
            </div>
            <nav className="flex-1 px-4 py-6 space-y-2">
              {menu.map((item) => (
                <Link href={item.path} key={item.name}>
                  <div
                    className="flex items-center space-x-2 p-3 rounded-lg cursor-pointer text-sm font-medium transition hover:bg-gray-100 text-gray-700"
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
                Logged in as <strong>User</strong> (Admin)
              </p>
              <button
                className="text-red-600 hover:underline"
              >
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
      </body>
    </html>
  )
}