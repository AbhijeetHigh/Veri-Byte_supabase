import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import UploadSection from './components/UploadSection';
import DatabaseProfiles from './components/DatabaseProfiles';
import PipelineStepper from './components/PipelineStepper';
import VerdictBadge from './components/VerdictBadge';
import MetricsRow from './components/MetricsRow';
import DeepfakeBreakdown from './components/DeepfakeBreakdown';
import ElaComparison from './components/ElaComparison';
import OcrInspector from './components/OcrInspector';
import ReportViewer from './components/ReportViewer';
import './App.css';

const INITIAL_STEP_STATES = {
  biometric: { status: 'pending', message: 'InsightFace Gatekeeper awaiting start' },
  deepfake: { status: 'pending', message: 'SigLIP Neural Detector awaiting start' },
  ocr: { status: 'pending', message: 'Tesseract OCR / MRZ extractor queued' },
  tampering: { status: 'pending', message: 'Error Level Analysis (ELA) queued' },
  verdict: { status: 'pending', message: 'Deterministic decision matrix queued' },
};

export default function App() {
  // Input State
  const [idFile, setIdFile] = useState(null);
  const [selfieFile, setSelfieFile] = useState(null);
  const [selfieDataUrl, setSelfieDataUrl] = useState(null);

  // Pipeline Execution State
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeStep, setActiveStep] = useState(null);
  const [stepStates, setStepStates] = useState(INITIAL_STEP_STATES);
  const [isComplete, setIsComplete] = useState(false);

  // Final Results State
  const [finalVerdict, setFinalVerdict] = useState(null);
  const [finalReport, setFinalReport] = useState(null);
  const [allResults, setAllResults] = useState({});
  const [elaBase64, setElaBase64] = useState(null);

  // Backend API Base URL (configurable via VITE_API_URL in production, defaults to relative /api)
  const API_BASE = import.meta.env.VITE_API_URL || '';

  // Backend API Status
  const [apiHealth, setApiHealth] = useState(null);

  // Check API health on mount & periodically
  const checkHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (res.ok) {
        const data = await res.json();
        setApiHealth(data);
      } else {
        setApiHealth({ status: 'error' });
      }
    } catch {
      setApiHealth({ status: 'error' });
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  // Reset entire application state
  const handleReset = () => {
    setIdFile(null);
    setSelfieFile(null);
    setSelfieDataUrl(null);
    setIsAnalyzing(false);
    setActiveStep(null);
    setStepStates(INITIAL_STEP_STATES);
    setIsComplete(false);
    setFinalVerdict(null);
    setFinalReport(null);
    setAllResults({});
    setElaBase64(null);
  };

  // Run Real-Time Streaming Analysis
  const handleAnalyze = async () => {
    if (!idFile || isAnalyzing) return;

    setIsAnalyzing(true);
    setIsComplete(false);
    setFinalVerdict(null);
    setFinalReport(null);
    setAllResults({});
    setElaBase64(null);
    setStepStates(INITIAL_STEP_STATES);

    const formData = new FormData();
    formData.append('id_file', idFile);
    if (selfieFile) {
      formData.append('selfie_file', selfieFile);
    } else if (selfieDataUrl) {
      formData.append('selfie_data', selfieDataUrl);
    }

    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let errDetail = 'Failed to analyze document';
        try {
          const errJson = await response.json();
          errDetail = errJson.detail || errDetail;
        } catch {}
        throw new Error(errDetail);
      }

      // Stream Server-Sent Events from backend
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const event of events) {
          const trimmed = event.trim();
          if (trimmed.startsWith('data: ')) {
            const jsonStr = trimmed.slice(6);
            try {
              const data = JSON.parse(jsonStr);
              handleIncomingStep(data);
            } catch (err) {
              console.error('Error parsing SSE event chunk:', err);
            }
          }
        }
      }
    } catch (err) {
      console.error('Analysis error:', err);
      setStepStates((prev) => ({
        ...prev,
        verdict: { status: 'error', message: err.message || 'Pipeline execution failed.' },
      }));
      setFinalVerdict('REJECT');
      setFinalReport(`# Pipeline Execution Error\n\nError: ${err.message}`);
    } finally {
      setIsAnalyzing(false);
      setIsComplete(true);
    }
  };

  // Process incoming stage updates
  const handleIncomingStep = (data) => {
    const { step, status, message } = data;
    setActiveStep(step);

    setStepStates((prev) => ({
      ...prev,
      [step]: { status, message },
    }));

    if (step === 'verdict' && status === 'complete') {
      setFinalVerdict(data.verdict || 'UNKNOWN');
      setFinalReport(data.report || '');
      setAllResults(data.results || {});
      if (data.ela_image_base64) {
        setElaBase64(data.ela_image_base64);
      }
    }
  };

  const hasResults = Boolean(finalVerdict);

  return (
    <div className="app-container">
      {/* Top Cyber Navigation & Status Header */}
      <Header apiHealth={apiHealth} onReset={handleReset} hasResults={hasResults} />

      {/* 5-Person National Identity Registry Profiles */}
      <DatabaseProfiles
        onSelectCard={(file) => setIdFile(file)}
        isAnalyzing={isAnalyzing}
      />

      {/* Input Upload & Live Camera Capture Section */}
      <UploadSection
        idFile={idFile}
        setIdFile={setIdFile}
        selfieFile={selfieFile}
        setSelfieFile={setSelfieFile}
        selfieDataUrl={selfieDataUrl}
        setSelfieDataUrl={setSelfieDataUrl}
        onAnalyze={handleAnalyze}
        isAnalyzing={isAnalyzing}
      />

      {/* Live 5-Step Pipeline Progress Indicator (Visible during or after analysis) */}
      {(isAnalyzing || hasResults) && (
        <PipelineStepper
          stepStates={stepStates}
          activeStep={activeStep}
          isComplete={isComplete}
        />
      )}

      {/* Post-Analysis Comprehensive Results Dashboard */}
      {hasResults && (
        <div className="results-container">
          {/* Glowing Verdict Banner */}
          <VerdictBadge
            verdict={finalVerdict}
            report={finalReport}
            results={allResults}
          />

          {/* 5 Core Forensic KPI Cards */}
          <MetricsRow results={allResults} />

          {/* Deepfake Ensemble Breakdown */}
          {allResults?.deepfake && (
            <DeepfakeBreakdown deepfake={allResults.deepfake} />
          )}

          {/* Error Level Analysis Visualizer */}
          <ElaComparison
            idFile={idFile}
            elaBase64={elaBase64}
            tampering={allResults?.tampering}
          />

          {/* OCR Structured Fields & Raw Dump */}
          {allResults?.ocr && <OcrInspector ocr={allResults.ocr} />}

          {/* Forensic Audit Report & Download */}
          <ReportViewer report={finalReport} verdict={finalVerdict} />
        </div>
      )}

      {/* Footer */}
      <footer className="footer-bar">
        <p>
          Veri-Byte SIH26188 — AI-Based Fake Identity &amp; Document Screening System
        </p>
        <p className="footer-sub">
          Ministry of Home Affairs &nbsp;|&nbsp; Blockchain &amp; Cybersecurity &nbsp;|&nbsp;
          Powered by FastAPI + React + InsightFace + SigLIP + Tesseract
        </p>
      </footer>
    </div>
  );
}
