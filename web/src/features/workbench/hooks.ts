/**
 * Feature: Test16-equivalent Workbench data hook.
 * Responsibilities: bind the permission-scoped dashboard projection to React Query.
 * Does not own: client-side authorization or business calculations.
 * Plan task: H5-MIGRATION-01.
 */

import { useQuery } from "@tanstack/react-query";

import { loadWorkbenchData } from "./api";

export function useWorkbenchData() {
  return useQuery({
    queryKey: ["workbench"],
    queryFn: loadWorkbenchData,
  });
}
