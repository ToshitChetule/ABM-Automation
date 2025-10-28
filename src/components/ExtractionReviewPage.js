import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

export default function ExtractionReviewPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const { uploadedFilename, columns: navColumns, rows: navRows } = location.state || {};
  const [columns, setColumns] = useState(navColumns || []);
  const [rows, setRows] = useState(navRows || []);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedRows, setSelectedRows] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [chatHistory, setChatHistory] = useState([]);

  const storedUser = JSON.parse(localStorage.getItem("user"));
  const username = storedUser?.username || "User";

  // ✅ Reprocess file if needed
  async function handleReprocess() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("http://localhost:5000/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: uploadedFilename }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || "Failed to re-process document.");
        setColumns([]);
        setRows([]);
      } else {
        setColumns(data.columns || []);
        setRows(data.rows || []);
      }
    } catch (e) {
      setError("Could not reach backend: " + e.message);
      setColumns([]);
      setRows([]);
    }
    setLoading(false);
  }

  // ✅ Refine selected rows only
  async function handleRefineAttributes() {
    if (selectedRows.length === 0) {
      alert("Please select at least one row to refine.");
      return;
    }
    if (!prompt.trim()) {
      alert("Please enter a refinement prompt.");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const selectedData = selectedRows.map((i) => rows[i]);

      // maintain chat memory
      const updatedChatHistory = [
        ...chatHistory,
        { role: "user", content: prompt.trim() },
      ];

      const response = await fetch("http://localhost:5000/refine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          selectedRows: selectedData,
          fullTable: rows,
          chatHistory: updatedChatHistory,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        alert(data.error || "Failed to refine attributes.");
        return;
      }

      const refinedRows = data.rows || [];

      // merge refined rows
      const updatedRows = [...rows];
      selectedRows.forEach((idx, i) => {
        if (refinedRows[i]) updatedRows[idx] = refinedRows[i];
      });

      setRows(updatedRows);
      setChatHistory(updatedChatHistory);
      setSelectedRows([]);
      setPrompt("");
      alert("✅ Attributes refined successfully!");
    } catch (err) {
      alert("Error refining attributes: " + err.message);
    } finally {
      setLoading(false);
    }
  }

  const filteredRows = rows.filter((row) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return row.some((cell) => String(cell).toLowerCase().includes(term));
  });

  if (!uploadedFilename || !columns || !rows) {
    return (
      <div
        style={{
          background: "linear-gradient(135deg,#dbeafe,#f3e8ff)",
          minHeight: "100vh",
          overflowY: "auto",
        }}
      >
        <header style={{ display: "flex", alignItems: "center", padding: "24px 24px" }}>
          <img
            src="https://img.icons8.com/fluency/96/000000/bot.png"
            alt="bot"
            style={{ width: 48, height: 48, marginRight: 16 }}
          />
          <h2 style={{ margin: 0, fontWeight: 700 }}>
            AI Extraction Automation - Extraction Result Review Page
          </h2>
        </header>
        <main
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "flex-start",
            marginTop: 40,
            paddingBottom: 60,
          }}
        >
          <div
            style={{
              color: "red",
              background: "rgba(255,255,255,0.7)",
              padding: 20,
              borderRadius: 10,
              boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
            }}
          >
            No file or extraction results found.<br />
            Redirecting to home...
          </div>
        </main>
      </div>
    );
  }

  return (
    <div
      style={{
        background: "linear-gradient(135deg,#f3e8ff,#dbeafe)",
        minHeight: "100vh",
        fontFamily: "'Inter', sans-serif",
        color: "#1e293b",
        overflowY: "auto",
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "center",
          padding: "24px 24px",
          background: "rgba(255,255,255,0.4)",
          backdropFilter: "blur(10px)",
          boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <img
          src="https://img.icons8.com/fluency/96/000000/bot.png"
          alt="bot"
          style={{ width: 48, height: 48, marginRight: 16 }}
        />
        <h2 style={{ margin: 0, fontWeight: 700, color: "#1e1e1e" }}>
          AI Extraction Automation - Extraction Result Review Page
        </h2>
        <span
          style={{
            marginLeft: "auto",
            background: "rgba(255,255,255,0.3)",
            padding: "8px 16px",
            borderRadius: 12,
            fontWeight: 600,
          }}
        >
          <h2>Hi {username} 👋</h2>
        </span>
      </header>

      <main
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "flex-start",
          marginTop: 40,
          paddingBottom: 60,
        }}
      >
        <div
          style={{
            width: "85%",
            background: "rgba(255,255,255,0.6)",
            borderRadius: 20,
            padding: 30,
            boxShadow: "0 8px 24px rgba(0,0,0,0.1)",
            backdropFilter: "blur(12px)",
            maxHeight: "80vh",
            overflowY: "auto",
          }}
        >
          <h3 style={{ color: "#1e40af", fontWeight: 700 }}>
            Extracted Data: {uploadedFilename}
          </h3>

          {/* 🔍 Search + Action Buttons */}
          <div style={{ marginBottom: 18, display: "flex", alignItems: "center", gap: 10 }}>
            <input
              placeholder="Search attributes"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                flex: 1,
                padding: "8px 14px",
                borderRadius: 8,
                border: "1px solid #94a3b8",
                outline: "none",
                transition: "0.3s all",
              }}
            />

            <button style={buttonStyle}>Approve Selected</button>
            <button onClick={handleReprocess} style={buttonStyle}>
              {loading ? "Re-processing..." : "Re-process"}
            </button>
            <button style={buttonStyle}>Export</button>
          </div>

          {/* 🧠 Prompt input + Refine Button */}
          <div style={{ marginBottom: 20, display: "flex", gap: 10 }}>
            <textarea
              placeholder="Write a prompt to refine selected attributes..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              style={{
                flex: 1,
                minHeight: 80,
                padding: "10px 14px",
                borderRadius: 8,
                border: "1px solid #94a3b8",
                resize: "vertical",
              }}
            />
            <button onClick={handleRefineAttributes} style={buttonStyle}>
              {loading ? "Refining..." : "Refine Attributes"}
            </button>
          </div>

          {error && <div style={{ color: "red", marginBottom: "12px" }}>{error}</div>}

          {/* 📊 Table */}
          <div
            style={{
              overflowX: "auto",
              borderRadius: 12,
              background: "rgba(255,255,255,0.4)",
              boxShadow: "inset 0 0 10px rgba(0,0,0,0.05)",
            }}
          >
            <table
              style={{
                borderCollapse: "collapse",
                width: "100%",
                background: "rgba(255,255,255,0.7)",
                borderRadius: 10,
                overflow: "hidden",
              }}
            >
              <thead>
                <tr>
                  <th style={{ ...thStyle, width: 40 }}></th>
                  {columns.map((col, idx) => (
                    <th key={idx} style={thStyle}>
                      {col}
                    </th>
                  ))}
                  <th style={thStyle}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row, ridx) => (
                  <tr
                    key={ridx}
                    style={{
                      transition: "0.3s",
                      background: selectedRows.includes(ridx)
                        ? "rgba(147,197,253,0.3)"
                        : "transparent",
                    }}
                  >
                    <td style={tdStyle}>
                      <input
                        type="checkbox"
                        checked={selectedRows.includes(ridx)}
                        onChange={(e) => {
                          const updated = e.target.checked
                            ? [...selectedRows, ridx]
                            : selectedRows.filter((id) => id !== ridx);
                          setSelectedRows(updated);
                        }}
                      />
                    </td>
                    {row.map((cell, cidx) => (
                      <td key={cidx} style={tdStyle}>
                        {cell}
                      </td>
                    ))}
                    <td style={tdStyle}>
                      <button disabled style={{ ...buttonStyle, opacity: 0.6, cursor: "not-allowed" }}>
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
                {filteredRows.length === 0 && (
                  <tr>
                    <td
                      colSpan={columns.length + 2}
                      style={{ textAlign: "center", padding: 18, color: "#64748b" }}
                    >
                      No matching attributes found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}

const buttonStyle = {
  marginRight: 10,
  padding: "8px 18px",
  borderRadius: 8,
  border: "none",
  background: "linear-gradient(135deg,#6366f1,#3b82f6)",
  color: "white",
  fontWeight: 600,
  cursor: "pointer",
  boxShadow: "0 4px 10px rgba(59,130,246,0.3)",
  transition: "all 0.25s ease",
};
const thStyle = {
  padding: 10,
  borderBottom: "2px solid #cbd5e1",
  background: "rgba(241,245,249,0.9)",
  fontWeight: "bold",
  color: "#1e293b",
  textAlign: "left",
};
const tdStyle = {
  padding: 8,
  borderBottom: "1px solid #e2e8f0",
  color: "#334155",
};
