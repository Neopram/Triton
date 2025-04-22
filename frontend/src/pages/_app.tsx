import "@/styles/globals.css";
import type { AppProps } from "next/app";
import { useRouter } from "next/router";
import ProtectedRoute from "@/components/ProtectedRoute";

// Define which routes don't require auth
const publicRoutes = ["/login"];

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();
  const isPublic = publicRoutes.includes(router.pathname);

  if (isPublic) {
    return <Component {...pageProps} />;
  }

  return (
    <ProtectedRoute>
      <Component {...pageProps} />
    </ProtectedRoute>
  );
}
