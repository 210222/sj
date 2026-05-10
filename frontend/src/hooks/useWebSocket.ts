/** useWebSocket — 实时推流 + 脉冲事件消费. */

import { useEffect, useRef, useCallback } from 'react';
import { createChatWebSocket } from '../api/client';

interface WSMessage {
  type: string;
  [key: string]: unknown;
}

interface UseWebSocketOptions {
  sessionId: string;
  onMessage: (msg: WSMessage) => void;
  onPulseEvent?: (msg: WSMessage) => void;
}

export function useWebSocket({ sessionId, onMessage, onPulseEvent }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    try {
      const ws = createChatWebSocket(sessionId);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data as string);
          if (msg.type === 'pulse_event') {
            onPulseEvent?.(msg);
          } else if (msg.type !== 'ping') {
            onMessage(msg);
          }
        } catch {
          // 忽略解析失败的消息
        }
      };

      ws.onclose = () => {
        // 5 秒后重连
        reconnectTimer.current = setTimeout(connect, 5000);
      };
    } catch {
      reconnectTimer.current = setTimeout(connect, 5000);
    }
  }, [sessionId, onMessage, onPulseEvent]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  const send = useCallback((msg: WSMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { send };
}
