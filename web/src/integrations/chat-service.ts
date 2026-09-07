/**
 * Feature: H5 ChatService voice transcription gateway.
 * Responsibilities: obtain a short-lived task-intake token and send browser recordings to ChatService ASR.
 * Does not own: user authentication, task persistence, LLM secrets, or business validation.
 * Migration: H5 Web V1.
 */

import { issueAiToken } from "../api/endpoints";

type ChatServiceEnvelope<T> = {
  success?: boolean;
  data?: T;
  error?: { code?: string; message?: string };
  message?: string;
};

type CachedToken = { token: string; expiresAt: number };
let cachedToken: CachedToken | null = null;
let tokenPromise: Promise<string> | null = null;

function chatServiceBaseUrl(): string {
  const value = import.meta.env.VITE_CHAT_SERVICE_BASE_URL?.trim();
  if (!value) throw new Error("语音服务尚未配置，请改用文字输入。");
  return value.replace(/\/$/, "");
}

async function taskIntakeToken(force = false): Promise<string> {
  const now = Date.now();
  if (!force && cachedToken && cachedToken.expiresAt > now + 30_000) return cachedToken.token;
  if (!force && tokenPromise) return tokenPromise;
  tokenPromise = issueAiToken()
    .then((result) => {
      cachedToken = {
        token: result.token,
        expiresAt: Date.now() + Math.max(30, result.expires_in || 300) * 1000,
      };
      return result.token;
    })
    .finally(() => {
      tokenPromise = null;
    });
  return tokenPromise;
}

function bytesToBase64(bytes: Uint8Array): string {
  const chunkSize = 0x8000;
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}

async function audioBase64(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  return bytesToBase64(new Uint8Array(buffer));
}

async function requestTranscription(blob: Blob, token: string): Promise<string> {
  const extension = blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") ? "m4a" : "webm";
  const response = await fetch(`${chatServiceBaseUrl()}/task-intake/transcribe`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      audioBase64: await audioBase64(blob),
      fileName: `voice.${extension}`,
    }),
  });
  const payload = (await response.json().catch(() => ({}))) as ChatServiceEnvelope<{ text?: string }>;
  if (!response.ok) {
    const error = new Error(payload.error?.message || payload.message || "语音转写失败，请改用文字输入。") as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  const text = payload.data?.text?.trim();
  if (!text) throw new Error("没有识别到有效语音，请重新录入或改用文字输入。");
  return text;
}

export async function transcribeBrowserRecording(blob: Blob): Promise<string> {
  try {
    return await requestTranscription(blob, await taskIntakeToken());
  } catch (error) {
    if ((error as { status?: number }).status !== 401) throw error;
    cachedToken = null;
    return requestTranscription(blob, await taskIntakeToken(true));
  }
}
