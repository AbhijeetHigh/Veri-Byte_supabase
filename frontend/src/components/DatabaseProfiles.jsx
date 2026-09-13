import React, { useState, useEffect } from 'react';

export default function DatabaseProfiles({ onSelectCard, isAnalyzing }) {
  const [citizens, setCitizens] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(true);
  const [activeCitizenId, setActiveCitizenId] = useState(null);
  const [loadingCardId, setLoadingCardId] = useState(null);

  const API_BASE = import.meta.env.VITE_API_URL || '';

  // Fetch registered citizens on mount
  useEffect(() => {
    fetchCitizens();
  }, []);

  const fetchCitizens = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/database/records`);
      if (res.ok) {
        const data = await res.json();
        setCitizens(data.records || []);
      }
    } catch (err) {
      console.warn('Failed to load database records:', err);
    } finally {
      setLoading(false);
    }
  };

  // Generate and load sample card for verification
  const handleLoadCard = async (citizen, docType) => {
    try {
      setLoadingCardId(`${citizen.id}-${docType}`);
      const res = await fetch(`${API_BASE}/api/database/sample-card/${citizen.id}?doc_type=${docType}`);
      if (!res.ok) throw new Error('Failed to generate sample card');
      const blob = await res.blob();
      const filename = `${citizen.name.replace(/\s+/g, '_')}_${docType}.jpg`;
      const file = new File([blob], filename, { type: 'image/jpeg' });
      setActiveCitizenId(citizen.id);
      onSelectCard(file);
    } catch (err) {
      console.error('Error loading sample card:', err);
      alert(`Failed to load card: ${err.message}`);
    } finally {
      setLoadingCardId(null);
    }
  };

  return (
    <div className="database-profiles-wrapper glass-panel animate-fade-in" style={{ marginBottom: '24px' }}>
      <div 
        className="db-header-bar" 
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
          padding: '12px 18px',
          borderBottom: isOpen ? '1px solid rgba(255, 255, 255, 0.1)' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '1.4rem' }}>🏛️</span>
          <div>
            <h3 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc', fontWeight: 600 }}>
              National Identity Database — 5 Registered Citizens
            </h3>
            <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8' }}>
              Official registry database for cross-verification &amp; testing (UIDAI / Income Tax / Election Commission)
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="badge badge-success" style={{ fontSize: '0.75rem', padding: '4px 10px' }}>
            {citizens.length} Citizens Active
          </span>
          <button 
            type="button" 
            className="toggle-expand-btn"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              fontSize: '1rem',
              cursor: 'pointer'
            }}
          >
            {isOpen ? '▲ Collapse' : '▼ View Profiles'}
          </button>
        </div>
      </div>

      {isOpen && (
        <div className="db-content-body" style={{ padding: '16px 18px' }}>
          <p style={{ fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '14px', lineHeight: 1.4 }}>
            Click <strong>"Load Aadhaar Card"</strong> or <strong>"Load PAN Card"</strong> below to automatically load a mathematically verified identity credential for any citizen directly into the forensic screening pipeline.
          </p>

          <div 
            className="citizens-cards-grid"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
              gap: '14px',
            }}
          >
            {citizens.map((citizen) => {
              const isSelected = activeCitizenId === citizen.id;
              const isAadhaarLoading = loadingCardId === `${citizen.id}-AADHAAR`;
              const isPanLoading = loadingCardId === `${citizen.id}-PAN`;
              const isPassportLoading = loadingCardId === `${citizen.id}-PASSPORT`;

              return (
                <div 
                  key={citizen.id}
                  className="citizen-item-card glass-panel"
                  style={{
                    padding: '14px',
                    borderRadius: '10px',
                    border: isSelected ? '1px solid #3b82f6' : '1px solid rgba(255, 255, 255, 0.08)',
                    background: isSelected ? 'rgba(59, 130, 246, 0.08)' : 'rgba(15, 23, 42, 0.6)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
                      <h4 style={{ margin: 0, fontSize: '0.95rem', color: '#60a5fa', fontWeight: 600 }}>
                        {citizen.name}
                      </h4>
                      <span className="badge badge-success" style={{ fontSize: '0.65rem' }}>
                        VERIFIED
                      </span>
                    </div>

                    <div style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.5, marginBottom: '10px' }}>
                      <div><strong>DOB:</strong> {citizen.dob_formatted} ({citizen.dob})</div>
                      <div><strong>Address:</strong> {citizen.address}</div>
                      <div><strong>Aadhaar:</strong> <code style={{ color: '#fca5a5' }}>{citizen.aadhaar_number}</code></div>
                      <div><strong>PAN:</strong> <code style={{ color: '#93c5fd' }}>{citizen.pan_number}</code></div>
                      <div><strong>Passport:</strong> <code style={{ color: '#a7f3d0' }}>{citizen.passport_number}</code> (Exp: {citizen.passport_expiry_date})</div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '6px', marginTop: '10px' }}>
                    <button
                      type="button"
                      disabled={isAnalyzing || Boolean(loadingCardId)}
                      onClick={() => handleLoadCard(citizen, 'AADHAAR')}
                      style={{
                        flex: 1,
                        padding: '6px 6px',
                        fontSize: '0.74rem',
                        fontWeight: 600,
                        borderRadius: '6px',
                        border: '1px solid rgba(239, 68, 68, 0.4)',
                        background: 'rgba(239, 68, 68, 0.15)',
                        color: '#fca5a5',
                        cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                        transition: 'all 0.2s',
                      }}
                      title="Load Aadhaar card into verification form"
                    >
                      {isAadhaarLoading ? '...' : '📄 Aadhaar'}
                    </button>

                    <button
                      type="button"
                      disabled={isAnalyzing || Boolean(loadingCardId)}
                      onClick={() => handleLoadCard(citizen, 'PAN')}
                      style={{
                        flex: 1,
                        padding: '6px 6px',
                        fontSize: '0.74rem',
                        fontWeight: 600,
                        borderRadius: '6px',
                        border: '1px solid rgba(59, 130, 246, 0.4)',
                        background: 'rgba(59, 130, 246, 0.15)',
                        color: '#93c5fd',
                        cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                        transition: 'all 0.2s',
                      }}
                      title="Load PAN card into verification form"
                    >
                      {isPanLoading ? '...' : '💳 PAN'}
                    </button>

                    <button
                      type="button"
                      disabled={isAnalyzing || Boolean(loadingCardId)}
                      onClick={() => handleLoadCard(citizen, 'PASSPORT')}
                      style={{
                        flex: 1,
                        padding: '6px 6px',
                        fontSize: '0.74rem',
                        fontWeight: 600,
                        borderRadius: '6px',
                        border: '1px solid rgba(16, 185, 129, 0.4)',
                        background: 'rgba(16, 185, 129, 0.15)',
                        color: '#a7f3d0',
                        cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                        transition: 'all 0.2s',
                      }}
                      title="Load Indian Passport biodata page into verification form"
                    >
                      {isPassportLoading ? '...' : '📘 Passport'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
