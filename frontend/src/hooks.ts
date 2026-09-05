import { useCallback, useEffect, useRef, useState } from 'react';
import { api, errorMessage } from './api';

/** Binds responses to their request path and ignores aborted, late responses. */
export function useApi<T>(path: string | null, pollMs = 0) {
  const [state, setState] = useState<{
    path: string | null;
    data: T | null;
    error: string;
    loading: boolean;
  }>({ path: null, data: null, error: '', loading: false });
  const [generation, setGeneration] = useState(0);
  const reload = useCallback(() => setGeneration((value) => value + 1), []);
  useEffect(() => {
    if (!path) return;
    const abort = new AbortController();
    setState((previous) => ({
      path,
      data: previous.path === path ? previous.data : null,
      error: '',
      loading: true,
    }));
    api<T>(path, { signal: abort.signal })
      .then((data) => {
        if (!abort.signal.aborted) setState({ path, data, error: '', loading: false });
      })
      .catch((failure: unknown) => {
        if (!abort.signal.aborted)
          setState((previous) => ({ ...previous, error: errorMessage(failure), loading: false }));
      });
    return () => abort.abort();
  }, [path, generation]);
  useEffect(() => {
    if (!pollMs || !path) return;
    const timer = window.setInterval(reload, pollMs);
    return () => window.clearInterval(timer);
  }, [pollMs, path, reload]);
  const current = state.path === path && path !== null;
  return {
    data: current ? state.data : null,
    error: current ? state.error : '',
    loading: !!path && (!current || state.loading),
    reload,
  };
}
export function useMounted() {
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  return mounted;
}
export function useDebounce(value: string, delay = 250) {
  const [result, setResult] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setResult(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return result;
}
