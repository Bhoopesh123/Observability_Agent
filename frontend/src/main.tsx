import React from "react";
import ReactDOM from "react-dom/client";
import { Activity, AlertTriangle, Bot, ChevronDown, Send, ServerCog, User } from "lucide-react";
import "./styles.css";

type Status = "healthy" | "warning" | "critical" | "unknown";

type ChatResponse = {
  answer: string;
  status: Status;
  confidence: "low" | "medium" | "high";
  key_findings: string[];
  recommendations: string[];
  sources: Record<string, unknown>;
  raw: Record<string, unknown>;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
};

const starterPrompts = [
  "Summarize system health",
  "Are there any active alerts?",
  "What is CPU usage in the last 30 minutes?",
  "Show error logs for service api"
];

const statusLabels: Record<Status, string> = {
  healthy: "Healthy",
  warning: "Warning",
  critical: "Critical",
  unknown: "Unknown"
};

function App() {
  const [messages, setMessages] = React.useState<Message[]>([
    {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "Ask me about Grafana alerts, dashboards, metrics, logs, or overall system health."
    }
  ]);
  const [input, setInput] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);
  const [activeConversation, setActiveConversation] = React.useState("Production health");

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed
    };

    setMessages((current) => [...current, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, conversation_id: activeConversation })
      });

      if (!response.ok) {
        throw new Error(`Backend returned HTTP ${response.status}`);
      }

      const data = (await response.json()) as ChatResponse;
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.answer,
          response: data
        }
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected request failure";
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `I could not reach the observability backend. ${message}`
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  function startNewConversation() {
    const name = `Investigation ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    setActiveConversation(name);
    setMessages([
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "New investigation started. What should I check first?"
      }
    ]);
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">
            <Activity size={20} />
          </div>
          <div>
            <strong>Observability Agent</strong>
            <span>Grafana-backed</span>
          </div>
        </div>

        <button className="newChatButton" onClick={startNewConversation}>
          <ServerCog size={17} />
          New investigation
        </button>

        <div className="conversationList">
          {["Production health", "Incident triage", "Capacity review"].map((item) => (
            <button
              key={item}
              className={item === activeConversation ? "conversation active" : "conversation"}
              onClick={() => setActiveConversation(item)}
            >
              {item}
            </button>
          ))}
        </div>
      </aside>

      <section className="chatPanel">
        <header className="topbar">
          <div>
            <h1>{activeConversation}</h1>
            <p>Supervisor agent routes questions to Grafana and summarizes the signal.</p>
          </div>
          <div className="connectionBadge">
            <span />
            localhost:8000
          </div>
        </header>

        <section className="messages" aria-live="polite">
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}
          {isLoading && (
            <div className="message assistant">
              <div className="avatar">
                <Bot size={18} />
              </div>
              <div className="bubble loadingBubble">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}
        </section>

        <div className="promptStrip">
          {starterPrompts.map((prompt) => (
            <button key={prompt} onClick={() => sendMessage(prompt)}>
              {prompt}
            </button>
          ))}
        </div>

        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            sendMessage(input);
          }}
        >
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendMessage(input);
              }
            }}
            placeholder="Ask about alerts, CPU, memory, dashboards, or error logs..."
            rows={1}
          />
          <button type="submit" disabled={isLoading || input.trim().length === 0} aria-label="Send message">
            <Send size={18} />
          </button>
        </form>
      </section>
    </main>
  );
}

function ChatMessage({ message }: { message: Message }) {
  const isAssistant = message.role === "assistant";

  return (
    <article className={isAssistant ? "message assistant" : "message user"}>
      <div className="avatar">{isAssistant ? <Bot size={18} /> : <User size={18} />}</div>
      <div className="bubble">
        <p>{message.content}</p>
        {message.response && <ResponseDetails response={message.response} />}
      </div>
    </article>
  );
}

function ResponseDetails({ response }: { response: ChatResponse }) {
  return (
    <div className="responseDetails">
      <div className={`statusPill ${response.status}`}>
        {response.status === "critical" && <AlertTriangle size={14} />}
        {statusLabels[response.status]}
        <span>{response.confidence} confidence</span>
      </div>

      {response.key_findings.length > 0 && (
        <section>
          <h2>Key Findings</h2>
          <ul>
            {response.key_findings.map((finding) => (
              <li key={finding}>{finding}</li>
            ))}
          </ul>
        </section>
      )}

      {response.recommendations.length > 0 && (
        <section>
          <h2>Next Steps</h2>
          <ul>
            {response.recommendations.map((recommendation) => (
              <li key={recommendation}>{recommendation}</li>
            ))}
          </ul>
        </section>
      )}

      <details>
        <summary>
          Technical details
          <ChevronDown size={15} />
        </summary>
        <pre>{JSON.stringify({ sources: response.sources, raw: response.raw }, null, 2)}</pre>
      </details>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
