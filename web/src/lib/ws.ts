/* ── Grokidding WebSocket Client ── */

import type { WSMessage, FarmStatus } from "./types";

type WSCallbacks = {
  onLog?: (line: string) => void;
  onProgress?: (data: FarmStatus) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
};

import Cookies from "js-cookie";

export class GrokWS {
  private ws: WebSocket | null = null;
  private url: string;
  private callbacks: WSCallbacks;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 10000;
  private destroyed = false;

  constructor(callbacks: WSCallbacks) {
    // WebSocket URL derived from current page origin
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const token = Cookies.get("auth_token") || "";
    this.url = `${proto}//${window.location.host}/ws?token=${token}`;
    this.callbacks = callbacks;
  }

  connect() {
    if (this.destroyed || this.ws) return;

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectDelay = 1000;
        this.callbacks.onConnect?.();
      };

      this.ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          switch (msg.type) {
            case "log":
              this.callbacks.onLog?.(msg.line);
              break;
            case "progress":
              this.callbacks.onProgress?.(msg.data);
              break;
          }
        } catch {
          // ignore parse errors
        }
      };

      this.ws.onclose = () => {
        this.ws = null;
        this.callbacks.onDisconnect?.();
        // Guard: jangan reconnect jika sudah di-destroy (component unmount)
        if (this.destroyed) return;
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.ws?.close();
      };
    } catch {
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.destroyed) return;
    if (this.reconnectTimer) return;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay);
      this.connect();
    }, this.reconnectDelay);
  }

  destroy() {
    this.destroyed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
