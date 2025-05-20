import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, ModuleRegistry } from "ag-grid-community";
import { useEffect, useMemo, useRef, useState } from "react";
import { Box } from "@mui/material";
import { MdOutlineCloudUpload } from "react-icons/md";
import { FaDownload } from "react-icons/fa";
import { MdDelete } from "react-icons/md";
import { RiChatNewLine } from "react-icons/ri";
import "../../css/navComponents/ProjectComponent.css";
import { useThreads } from "../../context/ThreadsContext";

export const ProjectComponent = () => {
  const { threads, setThreads, setCurrentThreadIndex, setSelectedItem } =
    useThreads();
  const inputUploadFieldRef = useRef(null);
  const [existingUploadedFiles, setExistingUploadedFiles] = useState([]);
  const [rowInfo, setRowinfo] = useState({
    selectedRow: null,
    isChecked: false,
  });

  const fetchData = async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/chat/uploadedFiles`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });
      const json = await res.json();
      setExistingUploadedFiles(json.uploadedFiles);
    } catch (error) {
      console.error("Error fetching uploaded files:", error);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  ModuleRegistry.registerModules([AllCommunityModule]);

  const rowSelection = useMemo(() => {
    return {
      mode: "singleRow",
    };
  }, []);

  const colDefs = useMemo(
    () => [
      { field: "filename", headerName: "FileName", flex: 1 },
      { field: "size", headerName: "FileSize", width: 100 },
      { field: "createdDate", headerName: "Uploaded On", flex: 1 },
      {
        headerName: "Actions",
        field: "file_id",
        cellRenderer: (params) => {
          const isCurrentRowSelected =
            rowInfo.isChecked &&
            rowInfo.selectedRow?.file_id === params.data.file_id;

          return (
            <div style={{ display: "flex", gap: "8px" }}>
              <FaDownload
                onClick={() => handleDownloadFile(params.value)}
                style={{
                  cursor: "pointer",
                  padding: "4px 8px",
                  background: "#2196f3",
                  color: "white",
                  border: "none",
                  borderRadius: "4px",
                  width: "2em",
                  height: "2em",
                }}
              />
              <MdDelete
                onClick={() => handleDeleteFile(params.value)}
                style={{
                  cursor: "pointer",
                  padding: "4px 8px",
                  background: "#f44336",
                  color: "white",
                  border: "none",
                  borderRadius: "4px",
                  width: "2.3em",
                  height: "2em",
                }}
              />
              <RiChatNewLine
                onClick={() =>
                  isCurrentRowSelected
                    ? handleNewChatFile(params)
                    : console.log(" Not the selected row")
                }
                style={{
                  cursor: isCurrentRowSelected ? "pointer" : "not-allowed",
                  background: isCurrentRowSelected ? "#f33446" : "#ccc",
                  color: "white",
                  border: "none",
                  borderRadius: "4px",
                  width: "2.3em",
                  height: "2em",
                  padding: "4px 8px",
                  pointerEvents: isCurrentRowSelected ? "auto" : "none",
                }}
              />
            </div>
          );
        },
        width: 200,
      },
    ],
    [rowInfo]
  );

  const handleOpenUploadPicker = () => {
    if (inputUploadFieldRef.current) {
      inputUploadFieldRef.current.click();
    }
  };

  const handleUploadFileInProjects = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", "your-session-id-here");

    try {
      const response = await fetch("http://127.0.0.1:8000/uploadfile", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        console.error("Upload error:", error.detail);
        return;
      }

      const result = await response.json();
      console.log("File uploaded:", result);
      fetchData();
    } catch (error) {
      console.error("Upload failed:", error);
    }
  };

  const handleDownloadFile = async (fileId) => {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/uploadedfiles/${fileId}/download`
      );
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "downloaded_file.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (error) {
      console.error("Download failed:", error);
    }
  };

  const handleDeleteFile = async (fileId) => {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/chat/delete/uploadedFiles/${fileId}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();
      console.log("Deleted:", data);

      fetchData();
    } catch (error) {
      console.error("Delete failed:", error);
    }
  };

  const handleNewChatFile = async (params) => {
    const file = params.data;

    const newThread = {
      sessionId: null,
      messages: [],
      name: `Thread ${threads.length + 1}`,
      pinned: false,
      fileAttachment: {
        file_id: file.file_id,
        filename: file.filename,
        fileSize: file.size,
        createdDate: file.createdDate,
      },
    };

    setThreads((prev) => [...prev, newThread]);
    setCurrentThreadIndex(threads.length);
    setSelectedItem("Collections");
  };

  return (
    <>
      <Box className="parent-container" sx={{ mt: 6 }}>
        <Box className="upload-container" onClick={handleOpenUploadPicker}>
          <Box>
            <MdOutlineCloudUpload className="upload-icon" />
          </Box>
          <Box>Files To Upload</Box>

          <input
            type="file"
            ref={inputUploadFieldRef}
            onChange={handleUploadFileInProjects}
            style={{ display: "none" }}
          />
        </Box>

        <Box style={{ marginTop: "20px", height: "350px", width: "100%" }}>
          <AgGridReact
            className="ag-theme-quartz"
            rowSelection={rowSelection}
            // rowData={existingUploadedFiles[0]?.uploadedFiles || []}
            rowData={existingUploadedFiles || []}
            columnDefs={colDefs}
            animateRows={true}
            onSelectionChanged={(event) => {
              const selectedRows = event.api.getSelectedRows();
              if (selectedRows.length > 0) {
                setRowinfo({
                  selectedRow: selectedRows[0],
                  isChecked: true,
                });
              } else {
                setRowinfo({
                  selectedRow: selectedRows[0],
                  isChecked: false,
                });
              }
            }}
          />
        </Box>
      </Box>
    </>
  );
};

// 1. **Overall Summary:** What does this dataset represent? Can you summarize its key characteristics?
// 2. **Key Trends:** What are the most significant trends in this dataset? Are there seasonal patterns or sudden changes?
// 3. **Anomalies & Outliers:** Do you detect any extreme values or unusual data points? What might be causing them?
// 4. **Correlations:** Are there any strong relationships between different columns? What do they suggest?
// 5. **Data Issues:** Are there missing values, duplicates, or inconsistencies? How might they affect the analysis?
// 6. **Actionable Insights:** Based on the data, what steps would you recommend to improve business performance or decision-making?
