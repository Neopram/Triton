import { useEffect } from "react";
import { useRouter } from "next/router";
import { useAuthStore } from "@/store/authStore";
import Layout from "@/components/Layout";

export default function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { token } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (!token) {
      router.replace("/login");
    }
  }, [token]);

  if (!token) return null;

  return <Layout>{children}</Layout>;
}
