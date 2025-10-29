import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import * as XLSX from "xlsx";
import { jsPDF } from "jspdf";
import "jspdf-autotable";
import { saveAs } from "file-saver";

import { Document, Packer, Paragraph, Table, TableCell, TableRow, TextRun } from "docx";
import Swal from "sweetalert2";

export default function ExtractionReviewPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const { uploadedFilename, columns: navColumns, rows: navRows } = location.state || {};
  const [columns, setColumns] = useState(navColumns || []);
  const [rows, setRows] = useState(navRows || []);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [attributeSearch, setAttributeSearch] = useState("");
  const [valueSearch, setValueSearch] = useState("");
  const [selectedRows, setSelectedRows] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);

  const storedUser = JSON.parse(localStorage.getItem("user"));
  const username = storedUser?.username || "User";

  // ✅ Toggle Select All
  const toggleSelectAll = (checked) => {
    if (checked) {
      const allVisible = filteredRows.map((_, i) => rows.indexOf(filteredRows[i]));
      setSelectedRows(allVisible);
    } else {
      setSelectedRows([]);
    }
  };

  // ✅ Refine selected rows
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
      const updatedChatHistory = [...chatHistory, { role: "user", content: prompt.trim() }];

      const response = await fetch("http://localhost:5000/refine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          selectedRows: selectedData,
          fullTable: rows,
          chatHistory: updatedChatHistory,
          allRows: rows,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        alert(data.error || "Failed to refine attributes.");
        return;
      }

      // ✅ Smart handling — supports both full-table and partial refinement results
      if (Array.isArray(data.rows) && data.rows.length >= rows.length) {
        setRows(data.rows); // backend sent the full merged table
      } else {
        const refinedRows = data.rows || [];
        const updatedRows = [...rows];
        selectedRows.forEach((idx, i) => {
          if (refinedRows[i]) updatedRows[idx] = refinedRows[i];
        });
        setRows(updatedRows);
      }

      setChatHistory(updatedChatHistory);
      setSelectedRows([]);
      setPrompt("");

      // ✅ Beautiful success popup instead of alert
      Swal.fire({
        icon: "success",
        title: "Refinement Complete!",
        text: "Selected attributes have been refined successfully.",
        showConfirmButton: false,
        timer: 2000,
        background: "rgba(255,255,255,0.9)",
        color: "#1e293b",
      });
    } catch (err) {
      alert("Error refining attributes: " + err.message);
    } finally {
      setLoading(false);
    }
  }

  // ✅ Filter rows based on attribute + value search
  const filteredRows = rows.filter((row) => {
    const attributeMatch = attributeSearch
      ? String(row[0] || "").toLowerCase().includes(attributeSearch.toLowerCase())
      : true;

    const valueMatch = valueSearch
      ? String(row[1] || "").toLowerCase().includes(valueSearch.toLowerCase())
      : true;

    return attributeMatch && valueMatch;
  });

  const allSelected =
    filteredRows.length > 0 &&
    filteredRows.every((row) => selectedRows.includes(rows.indexOf(row)));

  const partiallySelected =
    selectedRows.length > 0 && !allSelected && selectedRows.length < filteredRows.length;

  // ✅ EXPORT FUNCTIONS
  const handleExport = (format) => {
    const data = rows.map((r) => Object.fromEntries(columns.map((c, i) => [c, r[i]])));

    switch (format) {
      case "xlsx": {
        const ws = XLSX.utils.json_to_sheet(data);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, "Data");
        XLSX.writeFile(wb, `${uploadedFilename || "output"}.xlsx`);
        break;
      }

      case "pdf": {
        const doc = new jsPDF();
        doc.text("Extracted Attributes", 14, 16);
        doc.autoTable({
          head: [columns],
          body: rows,
          startY: 20,
          styles: { fontSize: 8 },
        });
        doc.save(`${uploadedFilename || "output"}.pdf`);
        break;
      }

      case "docx": {
        const tableRows = rows.map(
          (r) =>
            new TableRow({
              children: r.map((cell) => new TableCell({ children: [new Paragraph(cell.toString())] })),
            })
        );

        const doc = new Document({
          sections: [
            {
              properties: {},
              children: [
                new Paragraph({ children: [new TextRun("Extracted Attributes")] }),
                new Table({
                  rows: [
                    new TableRow({
                      children: columns.map((c) => new TableCell({ children: [new Paragraph(c)] })),
                    }),
                    ...tableRows,
                  ],
                }),
              ],
            },
          ],
        });

        Packer.toBlob(doc).then((blob) => {
          saveAs(blob, `${uploadedFilename || "output"}.docx`);
        });
        break;
      }

      case "txt": {
        const text = [
          columns.join("\t"),
          ...rows.map((r) => r.join("\t")),
        ].join("\n");

        const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
        saveAs(blob, `${uploadedFilename || "output"}.txt`);
        break;
      }

      default:
        alert("Unsupported format");
    }

    setExportMenuOpen(false);
  };

  return (
    <div
      style={{
        background: "linear-gradient(135deg,#f3e8ff,#dbeafe)",
        minHeight: "100vh",
        fontFamily: "'Inter', sans-serif",
        color: "#1e293b",
        overflowX: "hidden",
        overflowY: "auto",
      }}
    >
      {/* HEADER */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          padding: "24px",
          background: "rgba(255,255,255,0.4)",
          backdropFilter: "blur(10px)",
          boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
          position: "sticky",
          top: 0,
          zIndex: 50,
        }}
      >
        <img
          src="https://img.icons8.com/fluency/96/000000/bot.png"
          alt="bot"
          style={{ width: 48, height: 48, marginRight: 16 }}
        />
        <h2 style={{ margin: 0, fontWeight: 700 }}>AI Extraction Automation - Review Page</h2>
        <span
          style={{
            marginLeft: "auto",
            background: "rgba(255,255,255,0.3)",
            padding: "8px 16px",
            borderRadius: 12,
            fontWeight: 600,
          }}
        >
          Hi {username} 👋
        </span>
      </header>

      {/* MAIN */}
      <main
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "flex-start",
          padding: "20px 0",
        }}
      >
        <div
          style={{
            width: "80%",
            background: "rgba(255,255,255,0.6)",
            borderRadius: 20,
            boxShadow: "0 8px 24px rgba(0,0,0,0.1)",
            backdropFilter: "blur(12px)",
          }}
        >
          {/* Sticky Controls */}
          <div
            style={{
              position: "sticky",
              top: 0,
              zIndex: 40,
              background: "rgba(255,255,255,0.85)",
              backdropFilter: "blur(8px)",
              padding: "16px 24px",
              borderBottom: "1px solid #e2e8f0",
            }}
          >
            <h3 style={{ color: "#1e40af", fontWeight: 700, marginBottom: 12 }}>
              Extracted Data: {uploadedFilename}
            </h3>

            {/* SEARCH + EXPORT */}
            <div
              style={{
                display: "flex",
                gap: 10,
                marginBottom: 10,
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", gap: 10, flex: 1 }}>
                <input
                  placeholder="Search by Attribute..."
                  value={attributeSearch}
                  onChange={(e) => setAttributeSearch(e.target.value)}
                  style={searchInputStyle}
                />
                <input
                  placeholder="Search by Value..."
                  value={valueSearch}
                  onChange={(e) => setValueSearch(e.target.value)}
                  style={searchInputStyle}
                />
              </div>

              <button style={buttonStyle}>Approve Selected</button>

              <div style={{ position: "relative" }}>
                <button
                  style={buttonStyle}
                  onClick={() => setExportMenuOpen(!exportMenuOpen)}
                >
                  Export ▼
                </button>
                {exportMenuOpen && (
                  <div
                    style={{
                      position: "absolute",
                      right: 0,
                      top: "110%",
                      background: "white",
                      boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                      borderRadius: 8,
                      overflow: "hidden",
                      zIndex: 100,
                    }}
                  >
                    {["xlsx", "pdf", "docx", "txt"].map((fmt) => (
                      <div
                        key={fmt}
                        onClick={() => handleExport(fmt)}
                        style={{
                          padding: "10px 16px",
                          cursor: "pointer",
                          borderBottom: "1px solid #eee",
                        }}
                      >
                        Export as {fmt.toUpperCase()}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* PROMPT SECTION */}
            <div style={{ display: "flex", gap: 10 }}>
              <textarea
                placeholder="Write a prompt to refine selected attributes..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                style={{
                  flex: 1,
                  minHeight: 70,
                  padding: "10px 14px",
                  borderRadius: 8,
                  border: "1px solid #94a3b8",
                  resize: "vertical",
                }}
              />
              <button onClick={handleRefineAttributes} style={RefineButtonStyle}>
                {loading ? "Refining..." : "Refine Attributes"}
              </button>
            </div>
          </div>

          <br />

          {/* TABLE */}
          <div
            style={{
              flex: 1,
              padding: "0 24px 24px 24px",
            }}
          >
            <div
              style={{
                maxHeight: "70vh",
                overflowY: "auto",
                overflowX: "auto",
                borderRadius: 12,
                border: "1px solid #e2e8f0",
                background: "rgba(255,255,255,0.85)",
                boxShadow: "0 4px 10px rgba(0,0,0,0.08)",
              }}
            >
              <table
                style={{
                  borderCollapse: "collapse",
                  width: "100%",
                  minWidth: "900px",
                  tableLayout: "fixed",
                  wordWrap: "break-word",
                  whiteSpace: "normal",
                }}
              >
                <thead
                  style={{
                    position: "sticky",
                    top: 0,
                    background: "rgba(248,250,252,0.98)",
                    backdropFilter: "blur(6px)",
                    zIndex: 30,
                  }}
                >
                  <tr>
                    <th style={{ ...thStyle, width: 40 }}>
                      <input
                        type="checkbox"
                        checked={allSelected}
                        ref={(el) => el && (el.indeterminate = partiallySelected)}
                        onChange={(e) => toggleSelectAll(e.target.checked)}
                      />
                    </th>
                    {columns.map((col, idx) => (
                      <th key={idx} style={{ ...thStyle, width: "180px" }}>
                        {col}
                      </th>
                    ))}
                    <th style={{ ...thStyle, width: "100px" }}>Action</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredRows.map((row, ridx) => {
                    const globalIndex = rows.indexOf(row);
                    return (
                      <tr
                        key={ridx}
                        style={{
                          transition: "0.3s",
                          background: selectedRows.includes(globalIndex)
                            ? "rgba(147,197,253,0.25)"
                            : "transparent",
                        }}
                      >
                        <td style={{ ...tdStyle, textAlign: "center" }}>
                          <input
                            type="checkbox"
                            checked={selectedRows.includes(globalIndex)}
                            onChange={(e) => {
                              const updated = e.target.checked
                                ? [...selectedRows, globalIndex]
                                : selectedRows.filter((id) => id !== globalIndex);
                              setSelectedRows(updated);
                            }}
                          />
                        </td>
                        {row.map((cell, cidx) => (
                          <td key={cidx} style={tdStyle}>
                            {cell}
                          </td>
                        ))}
                        <td style={{ ...tdStyle, textAlign: "center" }}>
                          <button
                            disabled
                            style={{ ...buttonStyle, opacity: 0.6, cursor: "not-allowed" }}
                          >
                            Edit
                          </button>
                        </td>
                      </tr>
                    );
                  })}

                  {filteredRows.length === 0 && (
                    <tr>
                      <td
                        colSpan={columns.length + 2}
                        style={{
                          textAlign: "center",
                          padding: 18,
                          color: "#64748b",
                        }}
                      >
                        No matching data found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

// ✅ Styles
const searchInputStyle = {
  flex: 1,
  padding: "10px 14px",
  borderRadius: "10px",
  border: "1px solid #cbd5e1",
  outline: "none",
  background: "rgba(255,255,255,0.7)",
  boxShadow: "0 2px 6px rgba(0,0,0,0.05)",
  fontSize: "15px",
};

const buttonStyle = {
  padding: "10px 20px",
  borderRadius: 8,
  border: "none",
  background: "linear-gradient(135deg,#6366f1,#3b82f6)",
  color: "white",
  fontWeight: 600,
  cursor: "pointer",
  boxShadow: "0 4px 10px rgba(59,130,246,0.3)",
  transition: "all 0.25s ease",
};

const RefineButtonStyle = {
  ...buttonStyle,
  height: "50px",
  marginTop: "15px",
};

const thStyle = {
  padding: 10,
  borderBottom: "2px solid #cbd5e1",
  fontWeight: "bold",
  color: "#1e293b",
  textAlign: "left",
};

const tdStyle = {
  padding: 8,
  borderBottom: "1px solid #e2e8f0",
  color: "#334155",
  wordWrap: "break-word",
};
