import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import ReactMarkdown from "react-markdown";
import "./styles.css";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

const TOOL_DEFINITIONS = [
  {
    name: "get_dataset_overview",
    label: "Dataset overview",
    description: "Rows, columns, data types, and missing values.",
    fields: [],
  },
  {
    name: "null_values",
    label: "Find missing values",
    description: "Count null values in every column.",
    fields: [],
  },
  {
    name: "summarize",
    label: "Summarize data",
    description: "Summary statistics for numerical columns.",
    fields: [],
  },
  {
    name: "clean_dataset",
    label: "Clean missing values",
    description: "Fill numerical gaps with medians and categorical gaps with modes.",
    fields: [],
  },
  {
    name: "scatter_plot",
    label: "Scatter plot",
    description: "Compare two columns with a scatter plot.",
    fields: [
      {
        key: "x_column",
        label: "X column",
        placeholder: "e.g. age",
      },
      {
        key: "y_column",
        label: "Y column",
        placeholder: "e.g. salary",
      },
    ],
  },
  {
    name: "histogram",
    label: "Histogram",
    description: "Visualize the distribution of one numerical column.",
    fields: [
      {
        key: "column",
        label: "Column",
        placeholder: "e.g. salary",
      },
    ],
  },
  {
    name: "line_plot",
    label: "Line plot",
    description: "Plot a column over its row index or another X column.",
    fields: [
      {
        key: "y_column",
        label: "Y column",
        placeholder: "e.g. sales",
      },
      {
        key: "x_column",
        label: "X column (optional)",
        placeholder: "e.g. month",
        optional: true,
      },
    ],
  },
  {
    name: "bar_chart",
    label: "Bar chart",
    description: "Aggregate a numerical value by category.",
    fields: [
      {
        key: "category_column",
        label: "Category column",
        placeholder: "e.g. department",
      },
      {
        key: "value_column",
        label: "Value column",
        placeholder: "e.g. revenue",
      },
    ],
  },
  {
    name: "delete_columns",
    label: "Delete columns",
    description: "Remove one or more columns (they can be restored later).",
    fields: [
      {
        key: "columns",
        label: "Columns (comma separated)",
        placeholder: "e.g. notes, unused_id",
      },
    ],
  },
  {
    name: "restore_columns",
    label: "Restore columns",
    description: "Restore deleted columns, or leave blank to restore all.",
    fields: [
      {
        key: "columns",
        label: "Columns (comma separated, optional)",
        placeholder: "Leave blank to restore all",
        optional: true,
      },
    ],
  },
];

function formatToolRequest(tool, values) {
  const args = {};

  tool.fields.forEach(({ key, optional }) => {
    const value = values[key]?.trim();

    if (!value && optional) {
      return;
    }

    if (key === "columns") {
      args[key] = value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    } else {
      args[key] = value;
    }
  });

  return `Use the ${tool.name} tool with these arguments: ${JSON.stringify(
    args
  )}. Return the tool result clearly and explain what it means.`;
}

function getChartUrl(metadata) {
  if (!metadata?.chart_id) {
    return null;
  }

  return `${API_URL}/api/charts/${metadata.chart_id}`;
}

function restoreMessage(message) {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    metadata: message.metadata || null,
    chart: getChartUrl(message.metadata),
    created_at: message.created_at,
  };
}

function App() {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [selectedTool, setSelectedTool] = useState(null);
  const [toolValues, setToolValues] = useState({});
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState("");
  const [lightboxSrc, setLightboxSrc] = useState(null);

  const fileInput = useRef(null);
  const endOfMessages = useRef(null);

  useEffect(() => {
    endOfMessages.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  useEffect(() => {
    if (!lightboxSrc) {
      return;
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setLightboxSrc(null);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [lightboxSrc]);

  const selectedToolDefinition = useMemo(
    () => TOOL_DEFINITIONS.find((tool) => tool.name === selectedTool),
    [selectedTool]
  );

  /*
   * ---------------------------------------------------------
   * LOAD EXISTING CONVERSATION
   * ---------------------------------------------------------
   *
   * This restores:
   * - text
   * - user messages
   * - assistant messages
   * - stored chart metadata
   * - previously generated charts
   */
  async function loadConversation(id) {
    if (!id) {
      return;
    }

    setLoadingHistory(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/api/conversations/${id}/messages`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Could not load conversation history."
        );
      }

      const restoredMessages = data.map(restoreMessage);

      setConversationId(id);
      setMessages(restoredMessages);
    } catch (requestError) {
      console.error("Failed to load conversation:", requestError);
      setError(requestError.message);
    } finally {
      setLoadingHistory(false);
    }
  }

  /*
   * ---------------------------------------------------------
   * SEND MESSAGE
   * ---------------------------------------------------------
   */
  async function sendMessage(content = draft) {
    const message = content.trim();

    if (!message || loading || loadingHistory) {
      return;
    }

    setError("");
    setDraft("");

    /*
     * Optimistically display the user message.
     */
    setMessages((current) => [
      ...current,
      {
        role: "user",
        content: message,
      },
    ]);

    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message,
          conversation_id: conversationId,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "The agent could not process that request."
        );
      }

      setConversationId(data.conversation_id);

      /*
       * New chart generated during this request.
       *
       * chart_base64 is preferred because it can be displayed
       * immediately.
       *
       * chart_url is the fallback.
       */
      const chart =
        data.chart_base64 ||
        (data.chart_url ? `${API_URL}${data.chart_url}` : null);

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.response,
          chart,
          metadata: data.chart_id
            ? {
                chart_id: data.chart_id,
              }
            : null,
        },
      ]);
    } catch (requestError) {
      console.error("Chat request failed:", requestError);

      setError(requestError.message);

      /*
       * Remove the optimistic user message if the request failed.
       */
      setMessages((current) => current.slice(0, -1));
    } finally {
      setLoading(false);
    }
  }

  /*
   * ---------------------------------------------------------
   * UPLOAD DATASET
   * ---------------------------------------------------------
   */
  async function uploadDataset(event) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setError("");
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_URL}/api/datasets/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Could not upload this CSV."
        );
      }

      setDataset(data);

      setMessages((current) => [
        ...current,
        {
          role: "system",
          content: `${data.filename} is ready. Ask a question or choose a tool.`,
        },
      ]);
    } catch (requestError) {
      console.error("Upload failed:", requestError);
      setError(requestError.message);
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  /*
   * ---------------------------------------------------------
   * TOOL SELECTION
   * ---------------------------------------------------------
   */
  function chooseTool(tool) {
    setSelectedTool(tool.name);
    setToolValues({});
  }

  /*
   * ---------------------------------------------------------
   * RUN TOOL
   * ---------------------------------------------------------
   */
  function runTool(event) {
    event.preventDefault();

    if (!selectedToolDefinition) {
      return;
    }

    const missingRequired = selectedToolDefinition.fields.some(
      ({ key, optional }) =>
        !optional && !toolValues[key]?.trim()
    );

    if (missingRequired) {
      setError(
        "Fill in every required tool argument before running it."
      );

      return;
    }

    setSelectedTool(null);

    sendMessage(
      formatToolRequest(
        selectedToolDefinition,
        toolValues
      )
    );
  }

  /*
   * ---------------------------------------------------------
   * RENDER
   * ---------------------------------------------------------
   */
  return (
    <div className="app-shell">
      {/* =====================================================
          SIDEBAR
          ===================================================== */}

      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">✦</span>

          <div>
            <strong>DataLens</strong>
            <small>AI DATA AGENT</small>
          </div>
        </div>

        <div className="sidebar-section">
          <p className="eyebrow">Workspace</p>

          <button
            className="upload-button"
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
          >
            <span>
              {uploading ? "Uploading..." : "Upload CSV"}
            </span>

            <span className="button-icon">↑</span>
          </button>

          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            onChange={uploadDataset}
            hidden
          />

          {dataset && (
            <div className="dataset-card">
              <span className="status-dot" />

              <div>
                <strong>{dataset.filename}</strong>

                <small>
                  {dataset.total_rows?.toLocaleString()} rows ·{" "}
                  {dataset.total_columns} columns
                </small>
              </div>
            </div>
          )}

          {!dataset && (
            <p className="helper-text">
              Upload a CSV to start exploring your data.
            </p>
          )}
        </div>

        <div className="sidebar-section tool-launcher">
          <p className="eyebrow">Actions</p>

          <button
            className="tools-button"
            onClick={() =>
              setSelectedTool(
                selectedTool
                  ? null
                  : "get_dataset_overview"
              )
            }
          >
            <span className="tool-symbol">⌘</span>
            <span>Open data tools</span>
            <span className="chevron">›</span>
          </button>

          <p className="helper-text">
            Run an exact tool from <code>tools.py</code> with
            guided arguments.
          </p>
        </div>

        <div className="sidebar-footer">
          <span className="status-dot" />

          API connected at{" "}
          <code>
            {API_URL.replace(/^https?:\/\//, "")}
          </code>
        </div>
      </aside>

      {/* =====================================================
          MAIN CONTENT
          ===================================================== */}

      <main className="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">AI DATA WORKSPACE</p>
            <h1>Ask your data anything.</h1>
          </div>

          <div className="connection-pill">
            <span className="status-dot" />

            {loadingHistory ? "Loading..." : "Ready"}
          </div>
        </header>

        <section
          className={`content-grid ${
            selectedToolDefinition ? "with-drawer" : ""
          }`}
        >
          {/* =================================================
              CHAT
              ================================================= */}

          <div className="chat-panel">
            <div className="messages">
              {messages.length === 0 && !loadingHistory && (
                <div className="empty-state">
                  <div className="empty-icon">✦</div>

                  <h2>Your data, in focus.</h2>

                  <p>
                    Upload a CSV and ask for insights, cleaning,
                    summaries, or visualizations. The agent will
                    choose the right tool for you.
                  </p>

                  <div className="suggestions">
                    {[
                      "Give me an overview of this dataset",
                      "Which columns have missing values?",
                      "Create a histogram for a numerical column",
                    ].map((suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() =>
                          sendMessage(suggestion)
                        }
                      >
                        {suggestion}

                        <span>→</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {loadingHistory && (
                <div className="empty-state">
                  <div className="empty-icon">✦</div>

                  <h2>Loading conversation...</h2>

                  <p>
                    Restoring your previous messages and charts.
                  </p>
                </div>
              )}

              {/* =================================================
                  MESSAGES
                  ================================================= */}

              {messages.map((message, index) => (
                <div
                  className={`message-row ${message.role}`}
                  key={
                    message.id ||
                    `${message.role}-${index}`
                  }
                >
                  <div className="avatar">
                    {message.role === "user"
                      ? "YU"
                      : message.role === "system"
                      ? "!"
                      : "✦"}
                  </div>

                  <div className="message-bubble">
                    <div className="message-label">
                      {message.role === "user"
                        ? "You"
                        : message.role === "system"
                        ? "System"
                        : "DataLens"}
                    </div>

                    <div className="message-content">
                      <ReactMarkdown
                        components={{
                          img: ({
                            node,
                            ...props
                          }) => {
                            const src =
                              props.src || "";

                            /*
                             * Don't allow the LLM to display
                             * fake Windows/local filesystem
                             * image paths.
                             */
                            if (
                              src.startsWith(
                                "http://"
                              ) ||
                              src.startsWith(
                                "https://"
                              ) ||
                              src.startsWith(
                                "data:image/"
                              )
                            ) {
                              return (
                                <img
                                  {...props}
                                  onClick={() =>
                                    setLightboxSrc(src)
                                  }
                                />
                              );
                            }

                            return null;
                          },
                        }}
                      >
                        {message.content}
                      </ReactMarkdown>
                    </div>

                    {/* =================================================
                        CHART
                        ================================================= */}

                    {message.chart && (
                      <img
                        className="chart-image"
                        src={message.chart}
                        alt="Chart generated from your dataset"
                        onClick={() =>
                          setLightboxSrc(message.chart)
                        }
                        onError={(event) => {
                          /*
                           * If the chart file no longer exists,
                           * hide the broken image instead of
                           * showing a broken-image icon.
                           */
                          event.currentTarget.style.display =
                            "none";
                        }}
                      />
                    )}
                  </div>
                </div>
              ))}

              {/* =================================================
                  TYPING INDICATOR
                  ================================================= */}

              {loading && (
                <div className="message-row assistant">
                  <div className="avatar">✦</div>

                  <div className="message-bubble typing">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              )}

              <div ref={endOfMessages} />
            </div>

            {/* =================================================
                ERROR
                ================================================= */}

            {error && (
              <div className="error-banner">
                {error}
              </div>
            )}

            {/* =================================================
                COMPOSER
                ================================================= */}

            <div className="composer">
              <textarea
                value={draft}
                onChange={(event) =>
                  setDraft(event.target.value)
                }
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.shiftKey
                  ) {
                    event.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder="Ask a question about your dataset..."
                rows={1}
                disabled={
                  loading ||
                  loadingHistory
                }
              />

              <button
                className="send-button"
                onClick={() => sendMessage()}
                disabled={
                  loading ||
                  loadingHistory ||
                  !draft.trim()
                }
              >
                ↑
              </button>

              <small>
                Press Enter to send · Shift + Enter for a new
                line
              </small>
            </div>
          </div>

          {/* =================================================
              TOOL DRAWER
              ================================================= */}

          {selectedToolDefinition && (
            <div className="tool-drawer">
              <div className="drawer-header">
                <div>
                  <p className="eyebrow">TOOLS.PY</p>
                  <h2>Run a tool</h2>
                </div>

                <button
                  className="close-button"
                  onClick={() =>
                    setSelectedTool(null)
                  }
                >
                  ×
                </button>
              </div>

              <div className="tool-list">
                {TOOL_DEFINITIONS.map((tool) => (
                  <button
                    key={tool.name}
                    className={`tool-option ${
                      tool.name === selectedTool
                        ? "active"
                        : ""
                    }`}
                    onClick={() =>
                      chooseTool(tool)
                    }
                  >
                    <span className="tool-option-icon">
                      {tool.name.includes("plot") ||
                      tool.name === "bar_chart"
                        ? "◒"
                        : "◇"}
                    </span>

                    <span>
                      <strong>{tool.label}</strong>

                      <small>
                        {tool.description}
                      </small>
                    </span>

                    <span>›</span>
                  </button>
                ))}
              </div>

              {/* =================================================
                  TOOL FORM
                  ================================================= */}

              <form
                className="tool-form"
                onSubmit={runTool}
              >
                <div className="selected-tool">
                  <span className="tool-symbol">
                    ⌘
                  </span>

                  <div>
                    <strong>
                      {selectedToolDefinition.label}
                    </strong>

                    <small>
                      {selectedToolDefinition.name}
                    </small>
                  </div>
                </div>

                {selectedToolDefinition.fields.length ===
                0 ? (
                  <p className="form-note">
                    This tool does not need any arguments.
                    It will use the active dataset.
                  </p>
                ) : (
                  selectedToolDefinition.fields.map(
                    ({
                      key,
                      label,
                      placeholder,
                      optional,
                    }) => (
                      <label key={key}>
                        {label}

                        {optional && (
                          <em> optional</em>
                        )}

                        <input
                          value={
                            toolValues[key] || ""
                          }
                          onChange={(event) =>
                            setToolValues(
                              (current) => ({
                                ...current,
                                [key]:
                                  event.target.value,
                              })
                            )
                          }
                          placeholder={placeholder}
                        />
                      </label>
                    )
                  )
                )}

                <button
                  className="run-button"
                  type="submit"
                >
                  Run{" "}
                  {selectedToolDefinition.label}

                  <span>→</span>
                </button>
              </form>
            </div>
          )}
        </section>
      </main>

      {/* =====================================================
          IMAGE LIGHTBOX
          ===================================================== */}

      {lightboxSrc && (
        <div
          className="lightbox-overlay"
          onClick={() => setLightboxSrc(null)}
        >
          <button
            className="lightbox-close"
            onClick={() => setLightboxSrc(null)}
          >
            ×
          </button>

          <img
            className="lightbox-image"
            src={lightboxSrc}
            alt="Expanded view"
            onClick={(event) => event.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);