import { useEffect, useRef, useState } from 'react';
import type { WsStageEvent } from '@/types';

interface StageStatus {
  stage: string;
  status: 'in_progress' | 'complete' | 'failed';
  timestamp: string;
}

interface UseProcessingStreamReturn {
  statuses: Map<string, StageStatus>;
  isConnected: boolean;
  error: string | null;
}

/**
 * SSE-based hook for real-time pipeline status updates.
 * Uses EventSource which provides automatic reconnection.
 */
export function useProcessingStream(jobId: string | null): UseProcessingStreamReturn {
  const [statuses, setStatuses] = useState<Map<string, StageStatus>>(new Map());
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const token = localStorage.getItem('rax_token') || '';
    const apiUrl = import.meta.env.VITE_API_URL;
    let url: string;
    if (apiUrl) {
      // Production: connect directly to backend host
      url = `${apiUrl}/api/pipeline/${jobId}/events?token=${encodeURIComponent(token)}`;
    } else {
      // Dev: same host via Vite proxy
      url = `/api/pipeline/${jobId}/events?token=${encodeURIComponent(token)}`;
    }

    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    es.onmessage = (event) => {
      try {
        const data: WsStageEvent = JSON.parse(event.data);
        setStatuses((prev) => {
          const next = new Map(prev);
          next.set(`${data.resume_id}:${data.stage}`, {
            stage: data.stage,
            status: data.status,
            timestamp: data.timestamp,
          });
          return next;
        });
      } catch {
        // Ignore non-JSON (keepalive comments are filtered by EventSource)
      }
    };

    es.onerror = () => {
      setIsConnected(false);
      // EventSource auto-reconnects — just flag the transient error
      setError('Connection interrupted — reconnecting…');
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [jobId]);

  return { statuses, isConnected, error };
}
