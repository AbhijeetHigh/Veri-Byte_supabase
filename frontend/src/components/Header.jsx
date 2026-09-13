import React from 'react';

export default function Header({ apiHealth, onReset, hasResults }) {
  const isHealthy = apiHealth?.status === 'healthy';

  return (
    <header className="header-card">
      <div className="header-glow"></div>
      <div className="header-content">
        <div className="header-brand">
          <div className="header-icon-container">
            <span className="header-icon">🔍</span>
            <div className="radar-ping"></div>
          </div>
          <div className="header-titles">
            <div className="header-badge-row">
              <span className="badge badge-info">SIH26188 Forensic Suite</span>
              <span className={`badge ${isHealthy ? 'badge-success' : 'badge-danger'}`}>
                <span className={`status-dot ${isHealthy ? 'dot-active' : 'dot-offline'}`}></span>
                {isHealthy ? 'FastAPI Backend Online' : 'Connecting API...'}
              </span>
            </div>
            <h1 className="header-title">Veri-Byte Document Inspector</h1>
            <p className="header-subtitle">
              AI-Based Fake Identity &amp; Document Screening System &nbsp;|&nbsp;
              Ministry of Home Affairs &nbsp;|&nbsp; Blockchain &amp; Cybersecurity
            </p>
          </div>
        </div>

        {hasResults && (
          <div className="header-actions">
            <button className="btn-secondary" onClick={onReset}>
              <span>🔄</span> Start New Inspection
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
