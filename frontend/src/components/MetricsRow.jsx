import React from 'react';

export default function MetricsRow({ results }) {
  const ocr = results?.ocr || {};
  const tamper = results?.tampering || {};
  const bio = results?.biometric || {};
  const deepfake = results?.deepfake || {};

  // 1. Document Type
  const docType = ocr.id_type || '—';

  // 2. OCR Confidence
  const ocrConf = typeof ocr.confidence === 'number' ? Math.round(ocr.confidence) : 0;

  // 3. Integrity Status
  const integrity = tamper.integrity_status || '—';
  let integrityClass = 'badge-info';
  if (integrity === 'CLEAN') integrityClass = 'badge-success';
  else if (integrity === 'SUSPICIOUS') integrityClass = 'badge-warning';
  else if (integrity === 'TAMPERED') integrityClass = 'badge-danger';

  // 4. Biometric Match
  const bioMatch = typeof bio.match_confidence === 'number' ? bio.match_confidence.toFixed(1) : null;
  const bioPassed = bio.raw_verified;

  // 5. Deepfake Check
  const dfConf = typeof deepfake.confidence === 'number' ? deepfake.confidence : null;
  let dfLabel = '—';
  let dfClass = 'badge-info';
  if (dfConf !== null) {
    if (dfConf > 80) {
      dfLabel = 'AI Generated';
      dfClass = 'badge-danger';
    } else if (dfConf > 66) {
      dfLabel = 'Suspicious';
      dfClass = 'badge-warning';
    } else {
      dfLabel = 'Real Photo';
      dfClass = 'badge-success';
    }
  }

  return (
    <div className="metrics-grid animate-fade-in">
      {/* 1. Document Type */}
      <div className="glass-panel metric-card">
        <div className="metric-header">
          <span className="metric-icon">📄</span>
          <span className="metric-label">Document Type</span>
        </div>
        <div className="metric-value-box">
          <span className="metric-main-value" title={docType}>{docType}</span>
          <span className={`metric-sub-value ${ocr.format_valid === false ? 'text-danger font-bold' : ocr.format_valid === true ? 'text-success' : ''}`}>
            {ocr.format_valid === false
              ? '❌ Format / Checksum Invalid'
              : ocr.format_valid === true
              ? '✓ Format Valid'
              : 'Format Check Pending'}
          </span>
        </div>
      </div>

      {/* 2. OCR Confidence */}
      <div className="glass-panel metric-card">
        <div className="metric-header">
          <span className="metric-icon">🔤</span>
          <span className="metric-label">OCR Confidence</span>
        </div>
        <div className="metric-value-box">
          <span className="metric-main-value">{ocrConf}%</span>
          <div className="mini-progress-bar">
            <div
              className={`mini-fill ${ocrConf >= 70 ? 'fill-good' : ocrConf >= 40 ? 'fill-warn' : 'fill-bad'}`}
              style={{ width: `${ocrConf}%` }}
            ></div>
          </div>
        </div>
      </div>

      {/* 3. Document Integrity */}
      <div className="glass-panel metric-card">
        <div className="metric-header">
          <span className="metric-icon">🔍</span>
          <span className="metric-label">Integrity Status</span>
        </div>
        <div className="metric-value-box">
          <span className={`badge ${integrityClass}`}>{integrity}</span>
          <span className="metric-sub-value">
            {tamper.flagged_zones?.length
              ? `${tamper.flagged_zones.length} zone(s) flagged`
              : 'Zero ELA artifacts detected'}
          </span>
        </div>
      </div>

      {/* 4. Biometric Match */}
      <div className="glass-panel metric-card">
        <div className="metric-header">
          <span className="metric-icon">👤</span>
          <span className="metric-label">Biometric Match</span>
        </div>
        <div className="metric-value-box">
          <span className="metric-main-value">
            {bio.document_only ? 'N/A' : bioMatch ? `${bioMatch}%` : 'Failed / Blocked'}
          </span>
          <span className={`metric-sub-value ${bio.document_only ? 'text-info' : bioPassed ? 'text-success' : 'text-danger'}`}>
            {bio.document_only ? 'ℹ Document-Only Screening' : bioPassed ? '✓ Gatekeeper (>50%) Passed' : '✕ Match Failed (<50%)'}
          </span>
        </div>
      </div>

      {/* 5. Deepfake / AI Check */}
      <div className="glass-panel metric-card">
        <div className="metric-header">
          <span className="metric-icon">🤖</span>
          <span className="metric-label">Deepfake Check</span>
        </div>
        <div className="metric-value-box">
          <span className={`badge ${dfClass}`}>{dfLabel}</span>
          <span className="metric-sub-value">
            {dfConf !== null ? `${dfConf.toFixed(1)}% AI possibility` : 'Detection pending'}
          </span>
        </div>
      </div>

      {/* 6. National Identity Database Cross-Verification */}
      <div className="glass-panel metric-card">
        <div className="metric-header">
          <span className="metric-icon">🏛️</span>
          <span className="metric-label">National Registry</span>
        </div>
        <div className="metric-value-box">
          {(() => {
            const db = ocr.database_verification || {};
            const status = db.status;
            let badgeClass = 'badge-info';
            let label = 'UNREGISTERED';
            let subText = 'Not in database (AI screened)';

            if (status === 'VERIFIED_MATCH' || (db.record_found && status !== 'DEMOGRAPHIC_MISMATCH')) {
              badgeClass = 'badge-success';
              label = 'REGISTERED';
              subText = db.matched_citizen?.name ? `✓ Found: ${db.matched_citizen.name}` : 'Found in database';
            } else if (status === 'DEMOGRAPHIC_MISMATCH') {
              badgeClass = 'badge-warning';
              label = 'DEMOGRAPHIC MISMATCH';
              subText = db.discrepancies?.[0] || 'Conflict with database record';
            }

            return (
              <>
                <span className={`badge ${badgeClass}`}>{label}</span>
                <span className="metric-sub-value" title={subText}>{subText}</span>
              </>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
