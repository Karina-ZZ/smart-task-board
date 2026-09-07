/** Test14: reassign is representable and labeled, but never a version-only mutation. */
import { describe, expect, expectTypeOf, it } from "vitest";
import { actionLabels, type TaskLifecycleAction } from "./taskActions";
import { actionLabels as detailLabels } from "../features/task-detail/format";

describe("Test14 reassign response contract", () => {
  it("labels the server action without opening an unsupported lifecycle call", () => {
    expect(actionLabels.reassign_task).toBe("\u66f4\u6362\u627f\u529e\u4eba");
    expect(detailLabels.reassign_task).toBe(actionLabels.reassign_task);
    expectTypeOf<Extract<TaskLifecycleAction, "reassign_task">>().toEqualTypeOf<never>();
  });
});
