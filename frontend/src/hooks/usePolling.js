import { useState, useEffect, useRef, useCallback } from "react";

export function usePolling(fetchFn, interval = 30000) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const fetchRef = useRef(fetchFn);
  fetchRef.current = fetchFn;

  const fetchData = useCallback(async () => {
    try {
      const result = await fetchRef.current();
      if (result && (result.detail === "Authentication required" || result.detail === "Not authenticated")) {
        setError("Session expired. Please refresh and login.");
        return;
      }
      setData(result);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, interval);
    return () => clearInterval(id);
  }, [fetchData, interval]);

  return { data, loading, error, lastUpdated, refetch: fetchData };
}
