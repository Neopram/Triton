import { create } from "zustand";
import { persist } from "zustand/middleware";

type UserRole = "admin" | "fleet_manager" | "operator" | "viewer";

interface AuthState {
  accessToken: string | null;
  user: {
    id: number;
    username: string;
    role: UserRole;
  } | null;
  isAuthenticated: boolean;
  login: (token: string, userData: any) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      user: null,
      isAuthenticated: false,
      login: (token, userData) => {
        localStorage.setItem("access_token", token);
        set({
          accessToken: token,
          user: {
            id: userData.id,
            username: userData.username,
            role: userData.role,
          },
          isAuthenticated: true,
        });
      },
      logout: () => {
        localStorage.removeItem("access_token");
        set({
          accessToken: null,
          user: null,
          isAuthenticated: false,
        });
      },
    }),
    {
      name: "auth-storage",
    }
  )
);
