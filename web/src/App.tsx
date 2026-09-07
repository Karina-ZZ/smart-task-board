import { QueryClientProvider } from "@tanstack/react-query";

import { queryClient } from "./app/query-client";
import { AppRoutes } from "./app/router";
import { AuthProvider } from "./auth/AuthContext";
import { ToastProvider } from "./shared/components";

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
