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
import CollapsibleCard from "./components/CollapsibleCard";
import WorkflowStatusCard from "./components/WorkflowStatusCard";

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
  const [currentNode, setCurrentNode] = useState(null);

  // NEW: toggle chat page
  const [showChat, setShowChat] = useState(false);

  function applyWorkflowResponse(data) {
    setThreadId(data.thread_id || "");
    setStatus(data.status || "");
    setWorkflowState(data.state || null);
    setInterrupt(data.interrupt ?? null);
  }

  function handleStreamEvent(payload) {
    if (payload.thread_id) {
      setThreadId(payload.thread_id);
    }

    if (payload.node) {
      setCurrentNode(payload.node);
    }
  }

  async function handleStart() {
    if (!mainFile) {
      alert("Please upload a master PDF first.");
      return;
    }

    try {
      setLoading(true);
      setCurrentNode("upload");
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
        setStatus("success");
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
        setStatus("success");
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
        setStatus("success");
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

          <WorkflowStatusCard
              currentNode={currentNode}
              status={status}
              interrupt={interrupt}
          />
          <InterruptPanel
            interrupt={interrupt}
            loading={loading}
            onResumeDecision1={handleResumeDecision1}
            onResumeDecision2={handleResumeDecision2}
          />
        </div>

        <div className="right-column">
          <CollapsibleCard
              title="PDF Preview"
              defaultOpen={true}
          >
              <PdfPreview file={mainFile}/>
          </CollapsibleCard>
          <CollapsibleCard
              title="Workflow Outputs"
              defaultOpen={true}
          >
              <ResultsPanel state={workflowState}/>
          </CollapsibleCard>
          <CollapsibleCard
              title="Raw State JSON"
              defaultOpen={false}
          >
              <JsonViewer data={workflowState}/>
          </CollapsibleCard>
        </div>
      </div>
    </div>
  );
}