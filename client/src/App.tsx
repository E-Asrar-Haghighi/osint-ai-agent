import React, { useState } from 'react';
import type { FormEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import './App.css';

function App() {
  const [query, setQuery] = useState('');
  const [logs, setLogs] = useState<string[]>([]);
  const [report, setReport] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!query || isLoading) return;

    setLogs([]);
    setReport('');
    setIsLoading(true);

    try {
      // Step 1: POST to start the investigation and get a thread_id
      const response = await fetch('http://localhost:8000/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        throw new Error('Failed to start investigation.');
      }

      const threadId = response.headers.get('X-Thread-ID');
      if (!threadId) {
        throw new Error('Could not get investigation thread ID from backend.');
      }

      // Step 2: Connect to the SSE stream using the thread_id
      const eventSource = new EventSource(`http://localhost:8000/stream/${threadId}`);

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.log) {
          setLogs((prevLogs) => [...prevLogs, data.log]);
        }
        if (data.report) {
          setReport(data.report);
          // The backend will close the stream, but we can close it here too
          eventSource.close();
          setIsLoading(false);
        }
      };

      eventSource.onerror = () => {
        setLogs((prevLogs) => [...prevLogs, 'ERROR: Connection to backend stream failed.']);
        eventSource.close();
        setIsLoading(false);
      };
      
      // The backend now sends a special 'close' event, but listening for 'onerror' 
      // and closing on final report is a robust client-side pattern.

    } catch (error) {
      const message = error instanceof Error ? error.message : 'An unknown error occurred.';
      setLogs((prevLogs) => [...prevLogs, `ERROR: ${message}`]);
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>OSINT AI Agent</h1>
        <form onSubmit={handleSubmit} className="query-form">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter person to investigate (e.g., John Smith)"
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Investigating...' : 'Start Investigation'}
          </button>
        </form>
      </header>

      <main className="App-main">
        <div className="log-panel">
          <h2>Investigation Log</h2>
          <div className="log-box">
            {logs.map((log, index) => (
              <p key={index} className={log.startsWith('ERROR') ? 'error' : ''}>
                {log}
              </p>
            ))}
          </div>
        </div>

        <div className="report-panel">
          <h2>Final Intelligence Report</h2>
          <div className="report-box">
            {isLoading && !report && <p>Generating report...</p>}
            {report && <ReactMarkdown>{report}</ReactMarkdown>}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
