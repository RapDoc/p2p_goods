import { useState } from "react";
import Header from "./components/Header";
import UploadCard from "./components/UploadCard";
import StatusCard from "./components/StatusCard";
import WorkflowStepper from "./components/WorkflowStepper";
import InterruptPanel from "./components/InterruptPanel";
import ResultsPanel from "./components/ResultsPanel";
import JsonViewer from "./components/JsonViewer";
import RagChat from "./components/RagChat";
import PdfPreview from "./components/PdfPreview";

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

  // NEW: toggle chat page
  const [showChat, setShowChat] = useState(false);

  function applyWorkflowResponse(data) {
    setThreadId(data.thread_id || "");
    setStatus(data.status || "");
    setWorkflowState(data.state || null);
    setInterrupt(data.interrupt ?? null);
  }

  function handleStreamEvent(payload) {
    // First event already includes thread_id
    if (payload.thread_id) {
      setThreadId(payload.thread_id);
    }

    // node progress updates
    if (payload.event === "node_done") {
      const nodeOrder = {
        quality: 2,
        classifier: 3,
        merge: 3,
        decision_1: 4,
        extraction: 5,
        extract_fields: 5,
        normalization: 6,
        matching: 7,
        rag_index: 7,
        decision_2: 8,
        approval: 9,
        communication: 9,
      };

      const step = nodeOrder[payload.node];
      if (step) {
        setSimulatedStep((prev) => Math.max(prev, step));
      }
    }
  }

  async function handleStart() {
    if (!mainFile) {
      alert("Please upload a master PDF first.");
      return;
    }

    try {
      setLoading(true);
      setSimulatedStep(1);
      setInterrupt(null);
      setWorkflowState(null);
      setStatus("started");

      const finalEvent = await orchestrateWorkflow(mainFile, handleStreamEvent);

      if (!finalEvent) {
        throw new Error("Workflow stream ended without a final event");
      }

      if (finalEvent.event === "interrupted") {
        setStatus("interrupted");
        setInterrupt(finalEvent.interrupt || null);
      } else if (finalEvent.event === "done") {
        setStatus(finalEvent.status || "done");
        setWorkflowState(finalEvent.state || null);
        setInterrupt(null);
        setSimulatedStep(9);
      }
    } catch (err) {
      console.error(err);
      alert(err.message || "Failed to start workflow");
    } finally {
      setLoading(false);
    }
  }

  async function handleResumeDecision1(files) {
    if (!threadId) return alert("No active thread found.");
    if (!files || files.length === 0) return alert("Please upload reupload files.");

    try {
      setLoading(true);

      const finalEvent = await resumeDecision1(threadId, files, handleStreamEvent);

      if (!finalEvent) {
        throw new Error("Resume stream ended without a final event");
      }

      if (finalEvent.event === "interrupted") {
        setStatus("interrupted");
        setInterrupt(finalEvent.interrupt || null);
      } else if (finalEvent.event === "done") {
        setStatus(finalEvent.status || "done");
        setWorkflowState(finalEvent.state || null);
        setInterrupt(null);
        setSimulatedStep(9);
      }
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

      const finalEvent = await resumeDecision2(
        threadId,
        approved,
        reason || "",
        handleStreamEvent
      );

      if (!finalEvent) {
        throw new Error("Approval resume stream ended without a final event");
      }

      if (finalEvent.event === "interrupted") {
        setStatus("interrupted");
        setInterrupt(finalEvent.interrupt || null);
      } else if (finalEvent.event === "done") {
        setStatus(finalEvent.status || "done");
        setWorkflowState(finalEvent.state || null);
        setInterrupt(null);
        setSimulatedStep(9);
      }
    } catch (err) {
      console.error(err);
      alert(err.message || "Failed to resume decision 2");
    } finally {
      setLoading(false);
    }
  }

  // CHAT VIEW
  if (showChat) {
    return (
      <div className="app-shell">
        <Header />
        <RagChat threadId={threadId} onBack={() => setShowChat(false)} />
      </div>
    );
  }

  // MAIN DASHBOARD VIEW
  return (
    <div className="app-shell">
      <Header />

      <div className="top-action-row">
        <button
          className="secondary-btn"
          onClick={() => {
            if (!threadId) {
              alert("Run a workflow first so the chat has a thread to query.");
              return;
            }
            setShowChat(true);
          }}
        >
          Open Document Chat
        </button>
      </div>

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
          <PdfPreview file={mainFile} />
          <ResultsPanel state={workflowState} />
          <JsonViewer data={workflowState} />
        </div>
      </div>
    </div>
  );
}