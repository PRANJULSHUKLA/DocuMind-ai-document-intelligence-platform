import React from "react";

import {
  Bot,
  FileText,
  Loader2,
  Send,
  Sparkles,
  User,
} from "lucide-react";

import { askDocument } from "../services/documentService";

export default function AIAssistant({
  fileId,
  filename,
  conversation, onConversationChange, onSourceSelect, askQuestion = askDocument,
}) {
  const [localQuestion, setLocalQuestion] =
    React.useState("");

  const [localMessages, setLocalMessages] =
    React.useState([]);

  const [loading, setLoading] =
    React.useState(false);

  const [error, setError] =
    React.useState("");

  const question = conversation?.question ?? localQuestion;
  const messages = conversation?.messages ?? localMessages;
  function setQuestion(value) {
    if (onConversationChange) onConversationChange(previous => ({ ...previous, question: value }));
    else setLocalQuestion(value);
  }
  function setMessages(updater) {
    if (onConversationChange) onConversationChange(previous => ({ ...previous, messages: updater(previous.messages || []) }));
    else setLocalMessages(updater);
  }

  async function handleAsk(
    event
  ) {
    event?.preventDefault();

    const trimmed =
      question.trim();

    if (!trimmed || !fileId) {
      return;
    }

    setError("");

    const userMessage = {
      id:
        Date.now() +
        "-user",
      role: "user",
      content: trimmed,
    };

    setMessages(
      (previous) => [
        ...previous,
        userMessage,
      ]
    );

    setQuestion("");
    setLoading(true);

    try {
      const result =
        await askQuestion(
          fileId,
          trimmed
        );

      const assistantMessage = {
        id:
          Date.now() +
          "-assistant",
        role: "assistant",
        content:
          result?.answer ||
          "I could not generate an answer.",
        sources:
          result?.sources || [],
        timing: {
          retrieval:
            result?.retrieval_time_ms,
          generation:
            result?.generation_time_ms,
          total:
            result?.total_time_ms,
        },
      };

      setMessages(
        (previous) => [
          ...previous,
          assistantMessage,
        ]
      );
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Unable to answer the question."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-[650px] flex-col rounded-3xl border border-zinc-200 bg-white shadow-sm">

      {/* Header */}

      <div className="border-b border-zinc-200 p-5">

        <div className="flex items-center gap-3">

          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-900 text-white">
            <Bot size={19} />
          </div>

          <div className="min-w-0">

            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              AI Assistant
            </p>

            <h2 className="truncate text-sm font-semibold text-zinc-900">
              {filename ||
                "Selected document"}
            </h2>

          </div>

        </div>

      </div>

      {/* Messages */}

      <div className="flex-1 space-y-5 overflow-y-auto p-5">

        {messages.length ===
        0 ? (
          <div className="flex min-h-[430px] items-center justify-center">

            <div className="max-w-md text-center">

              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-100 text-zinc-500">
                <Sparkles
                  size={24}
                />
              </div>

              <h3 className="mt-4 text-lg font-semibold">
                Ask anything about the document
              </h3>

              <p className="mt-2 text-sm leading-6 text-zinc-500">
                The assistant searches the
                document knowledge base and
                answers using the most relevant
                retrieved content.
              </p>

              <div className="mt-5 flex flex-wrap justify-center gap-2">

                {[
                  "What are the major risks?",
                  "What obligations are mentioned?",
                  "What information is missing?",
                ].map(
                  (suggestion) => (
                    <button
                      key={
                        suggestion
                      }
                      onClick={() =>
                        setQuestion(
                          suggestion
                        )
                      }
                      className="rounded-full border border-zinc-200 px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50"
                    >
                      {suggestion}
                    </button>
                  )
                )}

              </div>

            </div>

          </div>
        ) : (
          messages.map(
            (message) => (
              <Message
                key={message.id}
                message={message}
                onSourceSelect={onSourceSelect}
              />
            )
          )
        )}

        {loading && (
          <div className="flex gap-3">

            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-zinc-900 text-white">
              <Bot size={15} />
            </div>

            <div className="rounded-2xl bg-zinc-100 px-4 py-3">

              <div className="flex items-center gap-2 text-sm text-zinc-500">

                <Loader2
                  size={15}
                  className="animate-spin"
                />

                Searching document...

              </div>

            </div>

          </div>
        )}

      </div>

      {error && (
        <div className="mx-5 mb-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700">
          {error}
        </div>
      )}

      {/* Input */}

      <form
        onSubmit={
          handleAsk
        }
        className="border-t border-zinc-200 p-4"
      >

        <div className="flex items-end gap-2 rounded-2xl border border-zinc-200 bg-zinc-50 p-2">

          <textarea
            aria-label="Ask a question"
            value={question}
            onChange={(event) =>
              setQuestion(
                event.target.value
              )
            }
            placeholder="Ask a question about this document..."
            rows={2}
            className="min-h-[48px] flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-zinc-400"
          />

          <button
            type="submit"
            aria-label="Ask document"
            disabled={
              loading ||
              !question.trim()
            }
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-zinc-900 text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send size={16} />
          </button>

        </div>

      </form>

    </div>
  );
}

function Message({
  message, onSourceSelect,
}) {
  const isUser =
    message.role ===
    "user";

  return (
    <div
      className={`flex gap-3 ${
        isUser
          ? "justify-end"
          : ""
      }`}
    >

      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-zinc-900 text-white">
          <Bot size={15} />
        </div>
      )}

      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-zinc-900 text-white"
            : "bg-zinc-100 text-zinc-700"
        }`}
      >

        <div className="flex items-start gap-2">

          {isUser && (
            <User
              size={14}
              className="mt-0.5 shrink-0"
            />
          )}

          <p className="whitespace-pre-wrap text-sm leading-6">
            {message.content}
          </p>

        </div>

        {!isUser &&
          message.sources?.length >
            0 && (
            <div className="mt-4 border-t border-zinc-200 pt-3">

              <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                Sources
              </p>

              <div className="mt-2 space-y-2">

                {message.sources.map(
                  (
                    source,
                    index
                  ) => (
                    <button
                      type="button"
                      onClick={() => onSourceSelect?.(source)}
                      disabled={!onSourceSelect || !source.page_number}
                      aria-label={`Open ${source.filename || "document"} page ${source.page_number}`}
                      key={
                        `${source.chunk_index}-${index}`
                      }
                      className="flex w-full gap-2 rounded-xl border border-transparent bg-white p-2.5 text-left hover:border-zinc-400 focus-visible:outline-2 disabled:opacity-50"
                    >

                      <FileText
                        size={14}
                        className="mt-0.5 shrink-0 text-zinc-400"
                      />

                      <div className="min-w-0">

                        <p className="text-[11px] font-medium text-zinc-700">
                          {source.filename ||
                            "Document"}
                        </p>

                        <p className="mt-0.5 text-[10px] text-zinc-400">
                          Page{" "}
                          {source.page_number ??
                            "—"}{" "}
                          • Chunk{" "}
                          {source.chunk_index ??
                            "—"}
                        </p>

                      </div>

                    </button>
                  )
                )}

              </div>

            </div>
          )}

        {!isUser &&
          message.timing?.total !=
            null && (
            <p className="mt-3 text-[10px] text-zinc-400">
              Retrieved and generated in{" "}
              {Math.round(
                message.timing.total
              )}
              ms
            </p>
          )}

      </div>

    </div>
  );
}
