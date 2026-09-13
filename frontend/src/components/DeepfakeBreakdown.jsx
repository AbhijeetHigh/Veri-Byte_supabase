import React from 'react';

const SIGNAL_CONFIGS = [
  {
    key: 'neural_detector',
    name: 'Neural Classifier',
    model: 'prithivMLmods/deepfake-detector-model-v1',
    weight: '60%',
    desc: 'Fine-tuned SigLIP vision transformer detecting synthetic artifacts',
  },
  {
    key: 'texture_uniformity',
    name: 'Texture Uniformity',
    weight: '15%',
    desc: 'Measures unnatural variance in Laplacian local sharpness',
  },
  {
    key: 'fft_score',
    name: 'FFT Frequency Smoothness',
    weight: '10%',
    desc: 'Detects high-frequency sensor noise loss typical of GAN generators',
  },
  {
    key: 'skin_uniformity',
    name: 'Skin Tone Uniformity',
    weight: '10%',
    desc: 'Analyzes YCbCr chrominance variation in skin pixels',
  },
  {
    key: 'symmetry_score',
    name: 'Facial Landmark Symmetry',
    weight: '5%',
    desc: 'Evaluates horizontal bilateral symmetry across 68 landmark points',
  },
];

export default function DeepfakeBreakdown({ deepfake }) {
  if (!deepfake || !deepfake.signals) return null;

  const signals = deepfake.signals;
  const overallConf = typeof deepfake.confidence === 'number' ? deepfake.confidence : 0;

  return (
    <div className="glass-panel detail-card animate-fade-in">
      <div className="detail-card-header">
        <div className="detail-header-left">
          <span className="detail-icon">🤖</span>
          <div>
            <h3>Deepfake / AI-Generation Multi-Signal Ensemble</h3>
            <p>
              Ensemble classifier combining SigLIP neural vision with computer-vision heuristics
            </p>
          </div>
        </div>
        <div className="detail-header-right">
          <span className="badge badge-info">
            Model: {deepfake.model_name || 'prithivMLmods/deepfake-detector-model-v1'}
          </span>
        </div>
      </div>

      <div className="signals-grid">
        {SIGNAL_CONFIGS.map((sig) => {
          const val = typeof signals[sig.key] === 'number' ? signals[sig.key] : 0;
          const isHighRisk = val > 75;
          const isMidRisk = val > 50;

          return (
            <div key={sig.key} className="signal-item">
              <div className="signal-title-row">
                <div>
                  <span className="signal-name">{sig.name}</span>
                  <span className="signal-weight">Weight: {sig.weight}</span>
                </div>
                <span className={`signal-score ${isHighRisk ? 'score-high' : isMidRisk ? 'score-mid' : 'score-low'}`}>
                  {val.toFixed(1)}%
                </span>
              </div>

              <div className="signal-bar-track">
                <div
                  className={`signal-bar-fill ${isHighRisk ? 'fill-danger' : isMidRisk ? 'fill-warning' : 'fill-primary'}`}
                  style={{ width: `${Math.min(100, Math.max(2, val))}%` }}
                ></div>
              </div>

              <p className="signal-desc">{sig.desc}</p>
            </div>
          );
        })}
      </div>

      <div className="signal-footer-note">
        <span>⚡ Ensemble Decision Rule:</span> AI Confidence &gt; 80% yields instant REJECT; 66%–80% routes to MANUAL REVIEW.
      </div>
    </div>
  );
}
