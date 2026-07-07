"use client";

import { useState } from "react";
import { Upload, User, Rocket, X, Plus, ChevronRight, FileText, RefreshCw, Lock } from "lucide-react";
import { ChatInterface } from "@/components/organisms/ChatInterface";
import { TestPrompts } from "@/components/organisms/TestPrompts";
import { CitationPanel } from "@/components/organisms/CitationPanel";
import { PanelLeftOpen, PanelLeftClose } from "lucide-react";
import { useChatStream } from "@/hooks/useChatStream";
import { useParams, useRouter } from "next/navigation";
import { classNames } from "@/lib/utils";

type SidePanel = "none" | "documents" | "persona";

// Parse the combined persona string into 3 parts for display
function parsePersonaDisplay(persona: string): { role: string; behavior: string; boundary: string } {
  const roleMatch = persona.match(/Role:\s*([\s\S]*?)(?=\nBehavior:|$)/);
  const behaviorMatch = persona.match(/Behavior:\s*([\s\S]*?)(?=\nBoundary:|$)/);
  const boundaryMatch = persona.match(/Boundary:\s*([\s\S]*?)$/);
  return {
    role: roleMatch ? roleMatch[1].trim() : '',
    behavior: behaviorMatch ? behaviorMatch[1].trim() : '',
    boundary: boundaryMatch ? boundaryMatch[1].trim() : persona,
  };
}

export function PlaygroundLayout() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  // Route param is named "id" but is actually the projectId — the playground
  // page lives at /projects/[id]/playground, and chat is project-scoped.
  const { messages, isStreaming, sendMessage } = useChatStream(jobId);
  const [showCitations, setShowCitations] = useState(false);
  const [activePanel, setActivePanel] = useState<SidePanel>("none");
  const [persona] = useState(
    "Role: You are a professional customer support assistant.\nBehavior: Be concise, friendly, and accurate. Always greet users warmly.\nBoundary: Do not provide legal or medical advice. Redirect off-topic questions politely.",
  );
  const [documents, setDocuments] = useState<string[]>([
    "Customer Support QA.pdf",
    "Reference Guide.docx",
  ]);

  const parsedPersona = parsePersonaDisplay(persona);

  // Citations belong to whichever assistant message most recently finished
  // streaming — there's no separate "current citations" state from the backend,
  // it arrives as part of the final SSE event for that message.
  const lastAssistantMessage = [...messages].reverse().find((m) => m.role === 'assistant');
  const latestCitations = lastAssistantMessage?.citations ?? [];

  const handleTestPrompt = (prompt: string) => sendMessage(prompt);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    Array.from(files).forEach((f) => {
      setDocuments((prev) => [...prev, f.name]);
    });
    e.target.value = "";
  };

  const removeDocument = (name: string) => {
    setDocuments((prev) => prev.filter((d) => d !== name));
  };

  return (
    <div className="h-[calc(100vh-100px)] flex flex-col gap-3">
      {/* Top action bar */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <button
            onClick={() =>
              setActivePanel(activePanel === "documents" ? "none" : "documents")
            }
            className={classNames(
              "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border",
              activePanel === "documents"
                ? "bg-gold/15 border-gold/40 text-gold"
                : "bg-white/[0.04] border-white/[0.08] text-fern hover:text-ivory hover:border-white/20",
            )}
          >
            <Upload size={13} />
            Documents
          </button>
          <button
            onClick={() =>
              setActivePanel(activePanel === "persona" ? "none" : "persona")
            }
            className={classNames(
              "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border",
              activePanel === "persona"
                ? "bg-gold/15 border-gold/40 text-gold"
                : "bg-white/[0.04] border-white/[0.08] text-fern hover:text-ivory hover:border-white/20",
            )}
          >
            <User size={13} />
            Persona
          </button>
        </div>

        <button
          onClick={() => router.push(`/projects/${jobId}/deploy`)}
          className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-gold text-void text-xs font-semibold hover:bg-amber transition-colors"
        >
          <Rocket size={13} />
          Deploy Model
          <ChevronRight size={13} />
        </button>
      </div>

      {/* ── Documents Panel ── */}
      {activePanel === "documents" && (
        <div className="glass-card flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-ivory">Knowledge Documents</h3>
              <p className="text-xs text-fern mt-0.5">
                Extend your AI&apos;s knowledge by adding documents here. These are used as extra context during every conversation — great for providing updated FAQs, product manuals, or any new information not covered in training.
              </p>
            </div>
            <button onClick={() => setActivePanel("none")} className="ml-4 shrink-0">
              <X size={14} className="text-muted hover:text-ivory" />
            </button>
          </div>

          {/* Existing documents */}
          <div className="flex flex-col gap-1.5">
            {documents.map((doc) => (
              <div
                key={doc}
                className="flex items-center justify-between px-3 py-2 rounded-lg bg-[#121B16]/60 border border-white/[0.06]"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FileText size={13} className="text-gold shrink-0" />
                  <span className="text-xs text-ivory truncate">{doc}</span>
                </div>
                <button
                  onClick={() => removeDocument(doc)}
                  className="ml-3 shrink-0"
                  aria-label={`Remove ${doc}`}
                >
                  <X size={12} className="text-muted hover:text-rose transition-colors" />
                </button>
              </div>
            ))}
          </div>

          {/* Upload new */}
          <label className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-dashed border-white/[0.12] text-xs text-fern hover:text-ivory hover:border-gold/40 cursor-pointer transition-colors">
            <Plus size={13} />
            Add a document to extend knowledge
            <input
              type="file"
              className="hidden"
              multiple
              accept=".pdf,.docx,.txt,.csv"
              onChange={handleFileUpload}
            />
          </label>
        </div>
      )}

      {/* ── Persona Panel ── */}
      {activePanel === "persona" && (
        <div className="glass-card flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-ivory">Model Persona</h3>
              <p className="text-xs text-fern mt-0.5">
                The identity and behavior rules this AI was trained with.
              </p>
            </div>
            <button onClick={() => setActivePanel("none")}>
              <X size={14} className="text-muted hover:text-ivory" />
            </button>
          </div>

          {/* Read-only persona display — split into 3 labelled sections */}
          <div className="space-y-3">
            {[
              { label: "Role", value: parsedPersona.role },
              { label: "Behavior", value: parsedPersona.behavior },
              { label: "Boundary", value: parsedPersona.boundary },
            ].map(({ label, value }) => (
              <div key={label}>
                <p className="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-muted mb-1.5">
                  {label}
                </p>
                <div className="w-full bg-[#121B16]/60 border border-white/[0.06] rounded-lg px-3 py-2.5 text-xs text-ivory/80 font-mono leading-relaxed">
                  {value || <span className="text-muted italic">Not defined</span>}
                </div>
              </div>
            ))}
          </div>

          {/* Retune button — disabled until backend supports it */}
          <div className="flex items-center justify-between pt-1 border-t border-white/[0.06]">
            <p className="text-[0.65rem] text-muted flex items-center gap-1.5">
              <Lock size={10} />
              Retuning requires backend support
            </p>
            <button
              disabled
              title="Retune with new persona questions — coming soon"
              className={classNames(
                "flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold transition-colors",
                "bg-white/[0.04] border border-white/[0.08] text-muted cursor-not-allowed opacity-50"
              )}
            >
              <RefreshCw size={12} />
              Retune Persona
            </button>
          </div>
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-0">
        {/* History sidebar */}
        <div className="hidden lg:block lg:col-span-2">
          <div className="glass-card h-full flex flex-col">
            <h3 className="text-sm font-semibold text-ivory mb-4">History</h3>
            <div className="flex-1 overflow-y-auto">
              <p className="text-xs text-muted text-center py-8">
                No history yet
              </p>
            </div>
          </div>
        </div>

        {/* Chat */}
        <div className="col-span-1 lg:col-span-7 flex flex-col min-h-0">
          <ChatInterface
            messages={messages}
            isStreaming={isStreaming}
            onSendMessage={sendMessage}
            className="flex-1"
          />
        </div>

        {/* Right sidebar */}
        <div className="hidden lg:flex lg:col-span-3 flex-col gap-4 min-h-0">
          <TestPrompts projectId={jobId} onPromptClick={handleTestPrompt} />
          <div className="flex-1 glass-card overflow-y-auto">
            <h3 className="text-sm font-semibold text-ivory mb-3">Sources</h3>
            {latestCitations.length === 0 && (
              <p className="text-xs text-muted">No sources yet — ask a question to see citations.</p>
            )}
            {latestCitations.map((c) => (
              <div
                key={c.id}
                className="p-2.5 rounded-lg bg-[#121B16]/60 border border-white/[0.06] mb-2"
              >
                <p className="text-xs font-medium text-ivory">
                  {c.documentName}
                </p>
                <p className="text-[0.65rem] text-sage">{c.chapter}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Mobile citation toggle */}
      <button
        onClick={() => setShowCitations(!showCitations)}
        className="lg:hidden fixed bottom-4 right-4 z-30 w-10 h-10 rounded-full bg-gold/20 backdrop-blur-sm flex items-center justify-center"
      >
        {showCitations ? (
          <PanelLeftClose size={18} className="text-gold" />
        ) : (
          <PanelLeftOpen size={18} className="text-gold" />
        )}
      </button>

      <CitationPanel
        citations={latestCitations}
        isOpen={showCitations}
        onClose={() => setShowCitations(false)}
      />
    </div>
  );
}
