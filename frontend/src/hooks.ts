import { useCallback, useEffect, useState } from 'react';
import { api, errorMessage } from './api';
export function useApi<T>(path: string | null, pollMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [generation, setGeneration] = useState(0);
  const reload = useCallback(() => setGeneration((value) => value + 1), []);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    const abort = new AbortController();
    setLoading(true);
    setError('');
    api<T>(path, { signal: abort.signal })
      .then((result) => {
        setData(result);
        setLoading(false);
      })
      .catch((failure: unknown) => {
        if (!abort.signal.aborted) {
          setError(errorMessage(failure));
          setLoading(false);
        }
      });
    return () => abort.abort();
  }, [path, generation]);
  useEffect(() => {
    if (!pollMs) return;
    const timer = window.setInterval(reload, pollMs);
    return () => window.clearInterval(timer);
  }, [pollMs, reload]);
  return { data, setData, error, loading, reload };
}
export function useDebounce(value: string, delay = 250) {
  const [result, setResult] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setResult(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return result;
}
