import React, { useEffect } from 'react';
import confetti from 'canvas-confetti';

export default function VerdictBadge({ verdict, report, results }) {
  useEffect(() => {
    if (verdict === 'APPROVED') {
      try {
        confetti({
          particleCount: 80,
          spread: 70,
          origin: { y: 0.6 },
          colors: ['#10b981', '#06b6d4', '#6366f1'],
        });
      } catch (e) {
        // Confetti is purely aesthetic
      }
    }
  }, [verdict]);

  const isApproved = verdict === 'APPROVED';
  const isReject = verdict === 'REJECT';
  const isReview = verdict === 'MANUAL REVIEW';

  let configClass = 'verdict-review';
  let title = 'MANUAL REVIEW REQUIRED';
  let icon = '⚠️';
  let tag = 'Potential Anomaly Detected';

  if (isApproved) {
    configClass = 'verdict-approved';
    title = 'VERIFIED AUTHENTIC — APPROVED';
    icon = '🛡️';
    tag = 'Genuine Identity & Clean Document';
  } else if (isReject) {
    configClass = 'verdict-reject';
    title = 'DOCUMENT REJECTED';
    icon = '🚫';
    tag = 'Fast-Fail Gatekeeper Violation or Tampering Detected';
  }

  // Extract reasons from report or results
  const reportLines = report ? report.split('\n') : [];
  const reasonsIndex = reportLines.findIndex((line) => line.includes('## Reasoning'));
  const reasons = reasonsIndex !== -1 ? reportLines.slice(reasonsIndex + 1).filter((l) => l.startsWith('- ')) : [];

  return (
    <div className={`glass-panel verdict-banner ${configClass} animate-fade-in`}>
      <div className="verdict-banner-glow"></div>
      <div className="verdict-header-row">
        <div className="verdict-icon-container">
          <span className="verdict-big-icon">{icon}</span>
        </div>
        <div className="verdict-title-box">
          <div className="verdict-tag-pill">{tag}</div>
          <h2 className="verdict-main-title">{title}</h2>
        </div>
        <div className="verdict-badge-box">
          <span className="verdict-final-stamp">{verdict}</span>
        </div>
      </div>

      {reasons.length > 0 && (
        <div className="verdict-reasons-container">
          <h4>Decision Matrix Findings:</h4>
          <ul className="reasons-list">
            {reasons.map((r, i) => (
              <li key={i} className="reason-item">
                <span className="reason-bullet">›</span>
                <span>{r.replace(/^- /, '')}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
