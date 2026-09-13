import React, { useState } from 'react';

export default function ElaComparison({ idFile, elaBase64, tampering }) {
  const [viewMode, setViewMode] = useState('side-by-side'); // 'side-by-side' or 'slider'
  const [sliderPos, setSliderPos] = useState(50);

  if (!elaBase64 && !idFile) return null;

  const originalUrl = idFile ? URL.createObjectURL(idFile) : null;
  const flaggedZones = tampering?.flagged_zones || [];
  const criticalFlagged = tampering?.critical_flagged || [];
  const suspiciousSoftware = tampering?.suspicious_software;

  return (
    <div className="glass-panel detail-card animate-fade-in">
      <div className="detail-card-header">
        <div className="detail-header-left">
          <span className="detail-icon">🔬</span>
          <div>
            <h3>Error Level Analysis (ELA) &amp; Digital Forensics</h3>
            <p>Reveals compression anomalies, pixel-level splicing, and EXIF software tampering</p>
          </div>
        </div>
        <div className="detail-header-right">
          <div className="mode-toggle">
            <button
              className={`toggle-btn ${viewMode === 'side-by-side' ? 'active' : ''}`}
              onClick={() => setViewMode('side-by-side')}
            >
              Side-by-Side
            </button>
            <button
              className={`toggle-btn ${viewMode === 'slider' ? 'active' : ''}`}
              onClick={() => setViewMode('slider')}
            >
              Overlay Slider
            </button>
          </div>
        </div>
      </div>

      {/* Flagged Status Banner */}
      {(flaggedZones.length > 0 || suspiciousSoftware) && (
        <div className="tamper-alert-box">
          <div className="alert-title">⚠️ Forensic Anomalies Detected:</div>
          <div className="alert-tags">
            {suspiciousSoftware && (
              <span className="badge badge-danger">Editing Software: {suspiciousSoftware}</span>
            )}
            {criticalFlagged.map((zone) => (
              <span key={zone} className="badge badge-danger">Critical Field Tampered: {zone}</span>
            ))}
            {flaggedZones.filter((z) => !criticalFlagged.includes(z)).map((zone) => (
              <span key={zone} className="badge badge-warning">Flagged Zone: {zone}</span>
            ))}
          </div>
        </div>
      )}

      {/* Visual Displays */}
      {viewMode === 'side-by-side' ? (
        <div className="ela-side-by-side">
          <div className="ela-frame">
            <div className="frame-header">
              <span className="frame-title">Original Document</span>
              <span className="badge badge-info">Raw Upload</span>
            </div>
            <div className="frame-img-container">
              {originalUrl ? (
                <img src={originalUrl} alt="Original Document" className="ela-display-img" />
              ) : (
                <div className="img-placeholder">Original image not available</div>
              )}
            </div>
          </div>

          <div className="ela-frame">
            <div className="frame-header">
              <span className="frame-title">Error Level Analysis (ELA) Heatmap</span>
              <span className="badge badge-warning">High-pass Recompression (Q90)</span>
            </div>
            <div className="frame-img-container">
              {elaBase64 ? (
                <img src={elaBase64} alt="Error Level Analysis" className="ela-display-img" />
              ) : (
                <div className="img-placeholder">ELA visualization unavailable</div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="ela-slider-container">
          <div className="slider-view-wrapper">
            {originalUrl && <img src={originalUrl} alt="Original" className="slider-base-img" />}
            {elaBase64 && (
              <div
                className="slider-clip-box"
                style={{ clipPath: `inset(0 0 0 ${sliderPos}%)` }}
              >
                <img src={elaBase64} alt="ELA Heatmap" className="slider-overlay-img" />
              </div>
            )}
            <div className="slider-divider-line" style={{ left: `${sliderPos}%` }}>
              <div className="slider-handle">⇄</div>
            </div>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={sliderPos}
            onChange={(e) => setSliderPos(Number(e.target.value))}
            className="interactive-slider"
          />
          <div className="slider-labels">
            <span>◄ Original Document</span>
            <span>Drag slider to inspect manipulation</span>
            <span>ELA Heatmap ►</span>
          </div>
        </div>
      )}

      <div className="ela-caption-note">
        <strong>Forensic Reading:</strong> Error Level Analysis re-saves the image at 90% JPEG quality and measures per-pixel delta. Brighter, elevated luminance clusters signify regions added or edited with differing compression histories (e.g. pasted text or modified digits).
      </div>
    </div>
  );
}
