"use client";

import { useEffect, useState } from "react";

interface HealthResponse {
  status: string;
}

export default function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchHealth() {
      try {
        const response = await fetch("http://localhost:8000/api/v1/health");
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = (await response.json()) as HealthResponse;
        setHealth(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    }

    fetchHealth();
  }, []);

  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <h1>Scholarship Chatbot Admin</h1>
      <p>Backend health check through `/api/v1/health`.</p>

      {error ? (
        <div style={{ color: "crimson" }}>
          <strong>Unable to fetch health:</strong> {error}
        </div>
      ) : health ? (
        <div style={{ marginTop: "1rem", padding: "1rem", border: "1px solid #ccc", borderRadius: 8 }}>
          <p>
            <strong>Status:</strong> {health.status}
          </p>
        </div>
      ) : (
        <p>Loading health status...</p>
      )}
    </main>
  );
}
