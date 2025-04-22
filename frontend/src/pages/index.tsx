import { useEffect } from "react";
import { useRouter } from "next/router";
import { useAuthStore } from "@/store/authStore";

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated) {
      router.push("/dashboard");
    } else {
      router.push("/login");
    }
  }, [isAuthenticated]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-white flex items-center justify-center">
      <div className="text-center p-8">
        <h1 className="text-3xl md:text-5xl font-bold text-blue-800 mb-4">
          Maritime Intelligence Platform
        </h1>
        <p className="text-gray-600 text-sm md:text-base max-w-md mx-auto mb-6">
          Optimizing voyages, tracking fleet operations, reducing emissions, and empowering commercial decisions — all from one place.
        </p>
        <div className="animate-pulse text-blue-600 text-sm">Redirecting...</div>
      </div>
    </div>
  );
}
