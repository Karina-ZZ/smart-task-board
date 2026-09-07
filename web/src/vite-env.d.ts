/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AUTH_MODE?: "prototype" | "wecom";
  readonly VITE_WECOM_CORP_ID?: string;
  readonly VITE_WECOM_AGENT_ID?: string;
  readonly VITE_WECOM_REDIRECT_URI?: string;
  readonly VITE_CHAT_SERVICE_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
