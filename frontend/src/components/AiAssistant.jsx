import React from "react";

import { Bot, FileText, Loader2, Send, Sparkles, User } from "lucide-react";

import { askDocument } from "../services/documentService";

export default function AIAssistant({
  fileId,
  filename,
  conversation,
  onConversationChange,
  onSourceSelect,
  askQuestion = askDocument,
}) {
  const [localQuestion, setLocalQuestion] = React.useState("");

  const [localMessages, setLocalMessages] = React.useState([]);

  const [loading, setLoading] = React.useState(false);

  const [error, setError] = React.useState("");

  const question = conversation?.question ?? localQuestion;
  const messages = conversation?.messages ?? localMessages;
  function setQuestion(value) {
    if (onConversationChange)
      onConversationChange((previous) => ({ ...previous, question: value }));
    else setLocalQuestion(value);
  }
  function setMessages(updater) {
    if (onConversationChange)
      onConversationChange((previous) => ({
        ...previous,
        messages: updater(previous.messages || []),
      }));
    else setLocalMessages(updater);
  }

  async function handleAsk(event) {
    event?.preventDefault();

    const trimmed = question.trim();

    if (!trimmed || !fileId) {
      return;
    }

    setError("");

    const userMessage = {
      id: Date.now() + "-user",
      role: "user",
      content: trimmed,
    };

    setMessages((previous) => [...previous, userMessage]);

    setQuestion("");
    setLoading(true);

    try {
      const result = await askQuestion(fileId, trimmed);

      const assistantMessage = {
        id: Date.now() + "-assistant",
        role: "assistant",
        content: result?.answer || "I could not generate an answer.",
        sources: result?.sources || [],
        timing: {
          retrieval: result?.retrieval_time_ms,
          generation: result?.generation_time_ms,
          total: result?.total_time_ms,
        },
      };

      setMessages((previous) => [...previous, assistantMessage]);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Unable to answer the question.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-panel flex flex-col rounded-xl border border-line bg-surface shadow-sm">
      {/* Header */}

      <div className="border-b border-line p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-on-accent">
            <Bot size={19} />
          </div>

          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-wider text-secondary">
              AI Assistant
            </p>

            <h2 className="truncate text-sm font-semibold text-primary">
              {filename || "Selected document"}
            </h2>
          </div>
        </div>
      </div>

      {/* Messages */}

      <div className="chat-content flex-1 space-y-5 overflow-y-auto p-5">
        {messages.length === 0 ? (
          <div className="flex min-h-[280px] items-center justify-center">
            <div className="max-w-md text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-raised text-secondary">
                <Sparkles size={24} />
              </div>

              <h3 className="mt-4 text-lg font-semibold">
                Ask. Follow the evidence.
              </h3>

              <p className="mt-2 text-sm leading-6 text-secondary">
                The assistant searches the document knowledge base and answers
                using the most relevant retrieved content.
              </p>

              <div className="mt-5 flex flex-wrap justify-center gap-2">
                {[
                  "What are the major risks?",
                  "What obligations are mentioned?",
                  "What information is missing?",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setQuestion(suggestion)}
                    className="rounded-full border border-line px-3 py-1.5 text-xs text-secondary hover:bg-muted"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <Message
              key={message.id}
              message={message}
              onSourceSelect={onSourceSelect}
            />
          ))
        )}

        {loading && (
          <div className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-on-accent">
              <Bot size={15} />
            </div>

            <div className="rounded-2xl bg-raised px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-secondary">
                <Loader2 size={15} className="animate-spin" />
                Searching document evidence…
              </div>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="mx-5 mb-3 rounded-xl border border-danger bg-danger-soft px-4 py-3 text-xs text-danger"
        >
          {error}
        </div>
      )}

      {/* Input */}

      <form onSubmit={handleAsk} className="border-t border-line p-4">
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-muted p-2">
          <textarea
            aria-label="Ask a question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask a question about this document..."
            rows={2}
            className="min-w-0 min-h-[48px] flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-secondary"
          />

          <button
            type="submit"
            aria-label="Ask document"
            disabled={loading || !question.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent text-on-accent hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send size={16} />
          </button>
        </div>
      </form>
    </div>
  );
}

function Message({ message, onSourceSelect }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-on-accent">
          <Bot size={15} />
        </div>
      )}

      <div
        className={`min-w-0 max-w-[92%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-accent-soft text-primary border border-line"
            : "bg-muted text-primary border border-line"
        }`}
      >
        <div className="flex items-start gap-2">
          {isUser && <User size={14} className="mt-0.5 shrink-0" />}

          <p className="min-w-0 whitespace-pre-wrap text-sm leading-7">
            {message.content}
          </p>
        </div>

        {!isUser && message.sources?.length > 0 && (
          <div className="mt-4 border-t border-line pt-3">
            <p className="text-xs font-semibold tracking-wider text-secondary">
              Sources
            </p>

            <div className="mt-2 space-y-2">
              {message.sources.map((source, index) => (
                <button
                  type="button"
                  onClick={() => onSourceSelect?.(source)}
                  disabled={!onSourceSelect || !source.page_number}
                  aria-label={`Open ${source.filename || "document"} page ${source.page_number}`}
                  key={`${source.chunk_index}-${index}`}
                  className="flex w-full gap-2 rounded-xl border border-transparent bg-surface p-2.5 text-left hover:border-line focus-visible:outline-2 disabled:opacity-50"
                >
                  <FileText
                    size={14}
                    className="mt-0.5 shrink-0 text-secondary"
                  />

                  <div className="min-w-0">
                    <p className="text-xs font-medium text-primary">
                      {source.filename || "Document"}
                    </p>

                    <p className="mt-0.5 text-xs text-secondary">
                      Page {source.page_number ?? "—"} • Chunk{" "}
                      {source.chunk_index ?? "—"}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {!isUser && message.timing?.total != null && (
          <p className="mt-3 text-xs text-secondary">
            Retrieved and generated in {Math.round(message.timing.total)}
            ms
          </p>
        )}
      </div>
    </div>
  );
}
