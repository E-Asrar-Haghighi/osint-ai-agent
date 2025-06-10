import { useState } from 'react';

interface InvestigationStatus {
  status: 'idle' | 'running' | 'completed' | 'error';
  message?: string;
}

interface InvestigationReport {
  findings: string[];
  timestamp: string;
}

export const InvestigationView = () => {
  const [status, setStatus] = useState<InvestigationStatus>({ status: 'idle' });
  const [report, setReport] = useState<InvestigationReport | null>(null);

  const startInvestigation = async () => {
    setStatus({ status: 'running' });
    try {
      const response = await fetch('http://localhost:8000/investigate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: 'test' }), // TODO: Add proper query input
      });
      
      if (!response.ok) {
        throw new Error('Investigation failed');
      }

      const data = await response.json();
      setReport(data);
      setStatus({ status: 'completed' });
    } catch (error) {
      setStatus({ 
        status: 'error', 
        message: error instanceof Error ? error.message : 'Unknown error occurred' 
      });
    }
  };

  return (
    <div className="investigation-view">
      <h1>OSINT Investigation</h1>
      
      <div className="status-section">
        <h2>Status: {status.status}</h2>
        {status.message && <p className="error">{status.message}</p>}
      </div>

      <button 
        onClick={startInvestigation}
        disabled={status.status === 'running'}
      >
        {status.status === 'running' ? 'Running...' : 'Start Investigation'}
      </button>

      {report && (
        <div className="report-section">
          <h2>Investigation Report</h2>
          <p>Generated: {report.timestamp}</p>
          <ul>
            {report.findings.map((finding, index) => (
              <li key={index}>{finding}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}; 