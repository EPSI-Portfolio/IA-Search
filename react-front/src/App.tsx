import { useState } from "react";
import "./App.css";

type Result = { line: string; score: number; cluster: string };
type SearchResponse = { query: string; clusters: string[]; results: Result[] };

const API_URL = "http://localhost:8000";

function App() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function search() {
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error(`Backend error ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 800, margin: "40px auto", padding: "0 16px" }}>
      <h1>AI SEARCH</h1>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && search()}
        placeholder="Ask a question..."
        style={{ width: "70%", padding: 8, marginRight: 8 }}
      />
      <button onClick={search} disabled={loading}>
        {loading ? "Searching..." : "Search"}
      </button>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {data && (
        <>
          <p>Clusters searched: {data.clusters.join(", ")}</p>
          <ul style={{ textAlign: "left" }}>
            {data.results.map((r, i) => (
              <li key={i} style={{ marginBottom: 8 }}>
                {r.line}
                <br />
                <small>
                  {r.cluster} · score {r.score.toFixed(2)}
                </small>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export default App;