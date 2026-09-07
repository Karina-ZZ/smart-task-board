/**
 * Feature: Test16 creator step 1 - describe task.
 * Responsibilities: capture text or browser-recorded voice, call the real task-intake extraction endpoint, and hand the AI result to step 2.
 * Does not own: task confirmation, formal draft creation, sending, or decomposition.
 * Plan task: H5-MIGRATION-02.
 */

import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { submitTaskInput } from "../../api/endpoints";
import type { TaskInputType } from "../../api/types";
import { createReturnSource } from "../../app/return-state";
import { transcribeBrowserRecording } from "../../integrations/chat-service";
import { Button, useToast } from "../../shared/components";
import "./TaskCreateStartPage.css";

const DRAFT_KEY = "smarttaskboard.dev07.intake-draft";
const EXAMPLES = [
  "梳理Q2绩效面谈反馈，周五前给我原因和行动清单",
  "完成招聘月报数据复核，发现异常及时说明",
];

function readText() {
  try {
    const draft = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || "{}") as { rawText?: unknown };
    return typeof draft.rawText === "string" ? draft.rawText : "";
  } catch {
    return "";
  }
}

function saveText(rawText: string, inputId: string | null = null, intake: unknown = null) {
  sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ rawText, inputId, intake }));
}

export function TaskCreateStartPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { showToast } = useToast();
  const [text, setText] = useState(readText);
  const [inputType, setInputType] = useState<TaskInputType>("text");
  const [submitting, setSubmitting] = useState(false);
  const [voiceState, setVoiceState] = useState<"idle" | "listening" | "transcribing">("idle");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    saveText(text);
  }, [text]);

  useEffect(() => () => streamRef.current?.getTracks().forEach((track) => track.stop()), []);

  async function toggleVoice() {
    if (voiceState === "listening" && recorderRef.current) {
      recorderRef.current.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      showToast("当前企业微信环境不支持录音，请改用文字输入");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const chunks: BlobPart[] = [];
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      recorder.onerror = () => {
        stream.getTracks().forEach((track) => track.stop());
        setVoiceState("idle");
        showToast("录音失败，请改用文字输入");
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        recorderRef.current = null;
        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        if (!blob.size) {
          setVoiceState("idle");
          showToast("没有录到有效语音，请重新录入");
          return;
        }
        try {
          setVoiceState("transcribing");
          const transcript = await transcribeBrowserRecording(blob);
          setInputType("voice");
          setText(transcript);
          showToast("语音已转为文字");
        } catch (error) {
          showToast(error instanceof Error ? error.message : "语音转写失败，请改用文字输入");
        } finally {
          setVoiceState("idle");
        }
      };
      setVoiceState("listening");
      recorder.start();
    } catch {
      setVoiceState("idle");
      showToast("需要麦克风权限，请在企业微信中允许后重试");
    }
  }

  async function next() {
    const rawText = text.trim();
    if (!rawText) {
      showToast("请先描述任务");
      return;
    }
    setSubmitting(true);
    try {
      const result = await submitTaskInput({ input_type: inputType, raw_text: rawText, source_channel: "web" });
      saveText(rawText, result.input_id, result);
      navigate("/create/details", { state: { source: createReturnSource(location, "描述任务") } });
    } catch (error) {
      showToast(error instanceof Error ? error.message : "AI识别失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="stb-create-start" data-testid="create-start-page">
      <div className="stb-create-start__stepper" aria-label="创建任务第1步，共3步">
        <div className="is-active"><b>1</b><span>描述</span></div><i className="is-active" />
        <div><b>2</b><span>确认信息</span></div><i />
        <div><b>3</b><span>确认发送</span></div>
      </div>
      <div className="stb-create-start__assistant"><i>✦</i><span><b>AI任务助手</b><small>说清楚要做什么、谁负责、何时完成即可</small></span></div>
      <div className="stb-create-start__prompt">
        <textarea
          value={text}
          maxLength={1000}
          onChange={(event) => { setInputType("text"); setText(event.target.value); }}
          placeholder="例如：梳理Q2绩效面谈反馈，周五前输出原因分析和行动清单，由林雨欣承办…"
          aria-label="任务描述"
        />
        <div><span>{text.length} / 1000</span><button type="button" className={voiceState === "listening" ? "is-listening" : ""} onClick={() => void toggleVoice()}>{voiceState === "listening" ? "■ 停止录音" : voiceState === "transcribing" ? "… 语音转写" : "◉ 语音描述"}</button></div>
      </div>
      <h2>试试这样说</h2>
      <div className="stb-create-start__examples">
        {EXAMPLES.map((example) => <button type="button" key={example} onClick={() => { setInputType("text"); setText(example); }}><span>“{example}”</span><b>＋</b></button>)}
      </div>
      <div className="stb-create-start__notice"><i>i</i><span>创建人只确认任务级信息。任务发送后，由主承办人接受并触发AI节点拆解。</span></div>
      <div className="stb-create-start__actions"><Button loading={submitting} onClick={() => void next()}>识别任务信息 →</Button></div>
    </section>
  );
}
