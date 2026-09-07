/**
 * Feature: Test16 creator step 2 - confirm task information.
 * Responsibilities: restore the AI extraction, support multi-round clarification, and host the task-level confirmation form.
 * Does not own: final sending, node decomposition, or performance scoring.
 * Plan task: H5-MIGRATION-03.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { clarifyTaskInput, getTaskInputExtraction } from "../../api/endpoints";
import type { TaskIntakeResponse } from "../../api/types";
import { Button, Card, ErrorState, Skeleton, useToast } from "../../shared/components";
import { TaskCreateDetailsPanel } from "./TaskCreateDetailsPanel";
import "./TaskCreateDetailsPage.css";

const DRAFT_KEY = "smarttaskboard.dev07.intake-draft";

type StoredDraft = { rawText: string; inputId: string | null; intake: TaskIntakeResponse | null };

function readDraft(): StoredDraft {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || "{}") as Partial<StoredDraft>;
    return {
      rawText: typeof parsed.rawText === "string" ? parsed.rawText : "",
      inputId: typeof parsed.inputId === "string" ? parsed.inputId : null,
      intake: parsed.intake && typeof parsed.intake === "object" ? parsed.intake as TaskIntakeResponse : null,
    };
  } catch {
    return { rawText: "", inputId: null, intake: null };
  }
}

function saveDraft(value: StoredDraft) {
  sessionStorage.setItem(DRAFT_KEY, JSON.stringify(value));
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "AI整理失败，请稍后重试";
}

export function TaskCreateDetailsPage() {
  const restored = useMemo(readDraft, []);
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [intake, setIntake] = useState<TaskIntakeResponse | null>(restored.intake);
  const [answer, setAnswer] = useState("");
  const inputId = restored.inputId ?? intake?.input_id ?? null;
  const extraction = useQuery({
    queryKey: ["task-input-extraction", inputId],
    queryFn: () => getTaskInputExtraction(inputId || ""),
    enabled: Boolean(inputId),
    refetchInterval: (query) => {
      const status = query.state.data?.job_status;
      return status === "pending" || status === "running" ? 1000 : false;
    },
  });

  useEffect(() => {
    if (!extraction.data) return;
    setIntake(extraction.data);
    saveDraft({ rawText: restored.rawText, inputId: extraction.data.input_id, intake: extraction.data });
  }, [extraction.data, restored.rawText]);

  const clarify = useMutation({
    mutationFn: () => {
      if (!intake) throw new Error("请先完成任务识别");
      const text = answer.trim();
      if (!text) throw new Error("请先回答AI追问");
      return clarifyTaskInput(intake.input_id, { answers: { clarification_text: text } });
    },
    onSuccess: (result) => {
      setIntake(result);
      setAnswer("");
      saveDraft({ rawText: restored.rawText, inputId: result.input_id, intake: result });
      showToast("识别结果已更新");
    },
    onError: (error) => showToast(errorMessage(error)),
  });

  if (!inputId && !intake) {
    return <ErrorState title="没有可确认的任务信息" detail="请先返回第一步描述任务并完成AI识别。" action={<Button onClick={() => navigate("/create")}>返回描述任务</Button>} />;
  }
  if (extraction.isLoading && !intake) return <><Skeleton height={96} /><Skeleton height={320} /></>;
  if (extraction.isError && !intake) return <ErrorState title="任务信息加载失败" detail={errorMessage(extraction.error)} action={<Button onClick={() => void extraction.refetch()}>重新加载</Button>} />;
  if (!intake) return null;

  const questions = intake.confirm_questions ?? [];
  return (
    <section className="stb-create-details-page" data-testid="create-details-page">
      <div className="stb-create-details-page__stepper" aria-label="创建任务第2步，共3步">
        <div className="is-done"><b>1</b><span>描述</span></div><i className="is-done" />
        <div className="is-active"><b>2</b><span>确认信息</span></div><i />
        <div><b>3</b><span>确认发送</span></div>
      </div>

      {questions.length > 0 && (
        <Card title="AI需要你确认" className="stb-create-details-page__questions">
          <ol>{questions.map((question, index) => <li key={`${index}:${question}`}>{question}</li>)}</ol>
          <textarea value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="直接回答，例如：李总指李明，验收人是我本人…" />
          <Button loading={clarify.isPending} onClick={() => clarify.mutate()}>提交回答，让AI继续整理</Button>
          <small>AI追问只用于补齐信息；你已经在下方人工修改的字段最终以人工确认值为准。</small>
        </Card>
      )}

      <TaskCreateDetailsPanel intake={intake} />
    </section>
  );
}
