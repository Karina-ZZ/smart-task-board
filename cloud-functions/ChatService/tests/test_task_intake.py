"""Feature 05 ChatService task extraction/clarification contract test."""

from services.qwen_service import QwenService
from services.task_intake import normalize_result, run_intake

raw = {
    "taskDraft": {
        "taskName": "渠道月报",
        "taskDescription": "周五完成渠道月报",
        "estimatedHours": 8,
        "nodes": [{"nodeName": "should be removed"}],
    },
    "missingFields": ["reviewerEmployeeNo", "estimatedHours"],
    "lowConfidenceFields": [],
    "confirmQuestions": [{"field": "reviewerEmployeeNo", "question": "由谁验收？"}],
    "confidenceScore": 0.7,
}
normalized = normalize_result(raw)
assert "estimatedHours" not in normalized["taskDraft"]
assert "nodes" not in normalized["taskDraft"]
assert "estimatedHours" not in normalized["missingFields"]
assert normalized["confirmQuestions"] == ["由谁验收？"]

calls = []


def fake_completion(messages):
    calls.append(messages)
    content = (
        '{"taskDraft":{"taskName":"渠道月报","taskDescription":"周五完成渠道月报"},'
        '"missingFields":["reviewerEmployeeNo"],"lowConfidenceFields":[],'
        '"confirmQuestions":[{"question":"由谁验收？"}],"confidenceScore":0.8}'
    )
    return {"choices": [{"message": {"content": content}}]}


qwen = QwenService(completion_client=fake_completion)
payload = {
    "input": {"inputId": "IN001", "rawText": "周五完成渠道月报", "inputType": "text"},
    "currentUser": {"employeeNo": "E1001"},
    "candidateUsers": [],
}
result = run_intake(payload, clarification=False, qwen=qwen, external_user_key="E1001")
assert result["taskDraft"]["taskName"] == "渠道月报"
assert result["confirmQuestions"] == ["由谁验收？"]
assert result["provider"] == "qwen"
assert len(calls) == 1
print("ChatService test_task_intake.py: PASS")

from pathlib import Path
prompt = (
    Path(__file__).resolve().parents[1] / "prompts" / "task_intake.md"
).read_text(encoding="utf-8")
assert "禁止根据岗位、部门、技能、负荷、直属关系" in prompt
assert "用户没有明确提到主承办人" in prompt
