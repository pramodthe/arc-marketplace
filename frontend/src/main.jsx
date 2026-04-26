import React from "react"
import { createRoot } from "react-dom/client"
import "./index.css"

class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error("App render error:", error, info?.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            minHeight: "100vh",
            padding: 24,
            fontFamily: "system-ui, sans-serif",
            background: "#111",
            color: "#fecaca",
            maxWidth: 640,
            margin: "0 auto",
          }}
        >
          <h1 style={{ color: "#f87171", fontSize: "1.1rem" }}>Something went wrong</h1>
          <p style={{ color: "#d4d4d8", marginTop: 12, lineHeight: 1.5 }}>
            The UI crashed while rendering. Open the browser developer console (Console tab) for the stack trace.
          </p>
          <pre
            style={{
              marginTop: 16,
              padding: 12,
              background: "#0a0a0a",
              border: "1px solid #3f3f46",
              borderRadius: 8,
              color: "#e5e5e5",
              fontSize: 12,
              overflow: "auto",
              whiteSpace: "pre-wrap",
            }}
          >
            {String(this.state.error?.message || this.state.error)}
          </pre>
        </div>
      )
    }
    return this.props.children
  }
}

function showFatal(container, title, detail) {
  container.textContent = ""
  const wrap = document.createElement("div")
  wrap.style.cssText =
    "min-height:100vh;box-sizing:border-box;padding:24px;font-family:system-ui,sans-serif;background:#111;color:#fecaca"
  const h1 = document.createElement("h1")
  h1.textContent = title
  h1.style.cssText = "color:#f87171;font-size:1.1rem;margin:0 0 12px"
  const p = document.createElement("p")
  p.textContent = "Check the browser console for the full stack trace."
  p.style.cssText = "color:#d4d4d8;line-height:1.5;margin:0 0 12px"
  const pre = document.createElement("pre")
  pre.style.cssText =
    "background:#0a0a0a;border:1px solid #3f3f46;border-radius:8px;padding:12px;color:#e5e5e5;font-size:12px;white-space:pre-wrap;overflow:auto"
  pre.textContent = String(detail)
  wrap.appendChild(h1)
  wrap.appendChild(p)
  wrap.appendChild(pre)
  container.appendChild(wrap)
}

const container = document.getElementById("root")
if (!container) {
  document.body.innerHTML =
    '<p style="padding:24px;font-family:system-ui;background:#111;color:#f87171">Missing #root div.</p>'
} else {
  import("./App.jsx")
    .then(({ default: App }) => {
      const root = createRoot(container)
      root.render(
        <React.StrictMode>
          <RootErrorBoundary>
            <App />
          </RootErrorBoundary>
        </React.StrictMode>,
      )
    })
    .catch((err) => {
      console.error("Failed to load App:", err)
      showFatal(
        container,
        "Failed to load application",
        err?.message || err || "Unknown error (check console).",
      )
    })
}
