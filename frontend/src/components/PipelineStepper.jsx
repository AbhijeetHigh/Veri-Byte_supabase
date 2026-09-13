import React from 'react';

const STEPS = [
  { id: 'biometric', label: 'Biometric Gatekeeper', sub: 'InsightFace Match (>50%)' },
  { id: 'deepfake', label: 'Deepfake & AI Check', sub: 'SigLIP + Multi-signal CV' },
  { id: 'ocr', label: 'OCR & Text Extraction', sub: 'Tesseract / MRZ Validation' },
  { id: 'tampering', label: 'Forgery & ELA Analysis', sub: 'Compression & Metadata Check' },
  { id: 'verdict', label: 'Verdict & Report', sub: 'Deterministic Decision Matrix' },
];

export default function PipelineStepper({ stepStates, activeStep, isComplete }) {
  // Calculate completion percentage
  const completedCount = STEPS.filter((s) => stepStates[s.id]?.status === 'complete').length;
  const isError = STEPS.some((s) => stepStates[s.id]?.status === 'error');
  const progressPercent = Math.min(100, Math.round((completedCount / STEPS.length) * 100));

  return (
    <div className="glass-panel stepper-container animate-fade-in">
      <div className="stepper-header">
        <div>
          <h3>⚡ Forensic Pipeline Execution</h3>
          <p>Real-time autonomous screening agent activity</p>
        </div>
        <div className="stepper-progress-pill">
          <span>{isComplete ? 'Analysis Finished' : isError ? 'Fast-Fail Gatekeeper Blocked' : 'Processing Stage'}</span>
          <span className="progress-number">{progressPercent}%</span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="progress-track">
        <div
          className={`progress-fill ${isError ? 'progress-error' : isComplete ? 'progress-complete' : ''}`}
          style={{ width: `${Math.max(5, progressPercent)}%` }}
        ></div>
      </div>

      {/* Steps List */}
      <div className="steps-grid">
        {STEPS.map((step, index) => {
          const state = stepStates[step.id] || { status: 'pending', message: 'Waiting for previous stage...' };
          const isRunning = state.status === 'running';
          const isDone = state.status === 'complete';
          const isFailed = state.status === 'error';

          let statusClass = 'step-pending';
          if (isRunning) statusClass = 'step-running';
          if (isDone) statusClass = 'step-complete';
          if (isFailed) statusClass = 'step-error';

          return (
            <div key={step.id} className={`step-card ${statusClass}`}>
              <div className="step-card-top">
                <div className="step-number">0{index + 1}</div>
                <div className="step-status-icon">
                  {isRunning && (
                    <div className="step-spinner">
                      <div className="spinner-inner"></div>
                    </div>
                  )}
                  {isDone && <span className="icon-done">✓</span>}
                  {isFailed && <span className="icon-fail">✕</span>}
                  {!isRunning && !isDone && !isFailed && <span className="icon-pending">○</span>}
                </div>
              </div>

              <div className="step-info">
                <h4>{step.label}</h4>
                <span className="step-sub">{step.sub}</span>
              </div>

              <div className="step-live-msg">
                <span className="msg-dot"></span>
                <p title={state.message || ''}>{state.message || 'Queued'}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
