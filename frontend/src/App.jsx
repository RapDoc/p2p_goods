import { useState } from "react";
import Header from "./components/Header";
import UploadCard from "./components/UploadCard";
import StatusCard from "./components/StatusCard";
import WorkflowStepper from "./components/WorkflowStepper";
import InterruptPanel from "./components/InterruptPanel";
import ResultsPanel from "./components/ResultsPanel";
import JsonViewer from "./components/JsonViewer";

import {
  orchestrateWorkflow,
  resumeDecision1,
  resumeDecision2,
} from "./api/workflowApi";

import "./styles/app.css";

export default function App() {
  const [mainFile, setMainFile] = useState(null);
  const [threadId, setThreadId] = useState("");
  const [status, setStatus] = useState("");
  const [workflowState, setWorkflowState] = useState(null);
  const [interrupt, setInterrupt] = useState(null);
  const [loading, setLoading] = useState(false);
  const [simulatedStep, setSimulatedStep] = useState(0);

  function applyWorkflowResponse(data) {
    setThreadId(data.thread_id || "");
    setStatus(data.status || "");
    setWorkflowState(data.state || null);
    setInterrupt(data.interrupt || null);
  }
  function runSimulatedProgress() {
    setSimulatedStep(1);

    const timers = [
      setTimeout(() => setSimulatedStep(2), 1000),
      setTimeout(() => setSimulatedStep(3), 4000),
      setTimeout(() => setSimulatedStep(4), 6000),
      setTimeout(() => setSimulatedStep(5), 8000),
      setTimeout(() => setSimulatedStep(6), 9000),
      setTimeout(() => setSimulatedStep(7), 10000),
      setTimeout(() => setSimulatedStep(8), 13000),
    ];

    return timers;
  }
  async function handleStart() {
    if (!mainFile) {
      alert("Please upload a master PDF first.");
      return;
    }

    let timers = [];

    try {
      setLoading(true);
      setSimulatedStep(0);
      timers = runSimulatedProgress();

      const data = await orchestrateWorkflow(mainFile);

      applyWorkflowResponse(data);
      setSimulatedStep(9);
    } catch (err) {
      console.error(err);
      alert(err.message || "Failed to start workflow");
    } finally {
      setLoading(false);
      timers.forEach(clearTimeout);
    }
  }

  async function handleResumeDecision1(files) {
    if (!threadId) return alert("No active thread found.");
    if (!files || files.length === 0) return alert("Please upload reupload files.");

    try {
      setLoading(true);
      const data = await resumeDecision1(threadId, files);
      applyWorkflowResponse(data);
    } catch (err) {
      console.error(err);
      alert(err.message || "Failed to resume decision 1");
    } finally {
      setLoading(false);
    }
  }

  async function handleResumeDecision2(approved, reason) {
    if (!threadId) return alert("No active thread found.");

    try {
      setLoading(true);
      const data = await resumeDecision2(threadId, approved, reason || "");
      applyWorkflowResponse(data);
    } catch (err) {
      console.error(err);
      alert(err.message || "Failed to resume decision 2");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <Header />

      <div className="dashboard-grid">
        <div className="left-column">
          <UploadCard
            file={mainFile}
            setFile={setMainFile}
            onStart={handleStart}
            loading={loading}
          />

          <StatusCard
            threadId={threadId}
            status={status}
            interrupt={interrupt}
          />
          
          <WorkflowStepper
            status={status}
            state={workflowState}
            interrupt={interrupt}
            simulatedStep={simulatedStep}
          />

          <InterruptPanel
            interrupt={interrupt}
            loading={loading}
            onResumeDecision1={handleResumeDecision1}
            onResumeDecision2={handleResumeDecision2}
          />
        </div>

        <div className="right-column">
          <ResultsPanel state={workflowState} />
          <JsonViewer data={workflowState} />
        </div>
      </div>
    </div>
  );
}