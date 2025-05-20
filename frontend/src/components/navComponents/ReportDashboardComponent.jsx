import React, { Component, useEffect, useRef, useState } from "react";
import { Box, Button, Typography } from "@mui/material";
import html2pdf from "html2pdf.js";
import { FaFileAlt } from "react-icons/fa";
import "../../css/ReportDashboard.css";
import { GraphVisualPlotly } from "./GraphVisualPlotlyComponent";
import ReactMarkdown from "react-markdown";

export const ReportDashboard = () => {
  const componentRef = useRef();
  const [fetchReportChatData, setFetchReportChatData] = useState([]);

  const fetchReportChat = async () => {
    try {
      const response = await fetch(
        "http://127.0.0.1:8000/chat/getAddedCharts",
        {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        }
      );

      const json = await response.json();
      const { AddedChats } = json;
      setFetchReportChatData(AddedChats);
    } catch (error) {
      console.error("Fetch error:", error);
    }
  };

  useEffect(() => {
    fetchReportChat();
  }, []);

  const handleDownloadPDF = () => {
    const element = componentRef.current;
    const opt = {
      margin: [0.3, -2],
      filename: "ReportDashboard.pdf",
      pagebreak: {
        before: ".beforeClass",
        after: ["#after1", "#after2"],
        avoid: "img",
      },
      image: { type: "jpeg", quality: 0.98 },
      pagebreak: { mode: "avoid-all", before: "#page2el" },
      html2canvas: {
        scale: 4,
        useCORS: true,
      },
      jsPDF: { unit: "in", format: "a3", orientation: "portrait" },
    };
    html2pdf().from(element).set(opt).save();
  };

  return (
    <>
      <Box className="headingForReports">
        <h1>All Reports</h1>
      </Box>

      {/* <Box>
        <nav role="navigation" class="primary-navigation">
          <ul>
            <li><a href="#">--Select--</a>
              <ul class="dropdown">
                <li><a href="#">Web Development</a></li>
                <li><a href="#">Web Design</a></li>
                <li><a href="#">Illustration</a></li>
                <li><a href="#">Iconography</a></li>
              </ul>
            </li>
          </ul>
        </nav>
      </Box> */}

      <Box className="buttonForDownload">
        <Button
          variant="contained"
          color="primary"
          onClick={handleDownloadPDF}
          sx={{ mb: 2 }}
        >
          Download as PDF
        </Button>
      </Box>

      <Box
        className="parentOfReports"
        ref={componentRef}
        sx={{
          padding: 2,
          backgroundColor: "#fff",
          width: "794px",
          backgroundColor: "#fff",
          padding: 2,
          margin: "0 auto",
        }}
      >
        {fetchReportChatData.map((x, index) => {
          const extractResponse = x.response.res;
          // const displayAttribute = extractResponse.visualization.graphData.length < 5 &&
          //   extractResponse.visualization.graphData.length !== 0 ? 'flex' : ''
          return (
            <Box key={index} sx={{ mb: 2, padding: 1 }}>
              <div
                className="questionInReportDashboard"
                style={{
                  width: "fit-content",
                  marginBottom: "8px",
                }}
              >
                <div className="question">
                  {x.AddedChats && (
                    <Box
                      className="upload-file-container"
                      sx={{ display: "flex", borderRadius: "20px" }}
                    >
                      <Box className="file-icon">
                        <FaFileAlt />
                      </Box>
                      <Box sx={{ margin: "8px" }}>
                        <Typography>{x.questionName}</Typography>
                      </Box>
                    </Box>
                  )}
                  {x.questionName}
                </div>
              </div>

              {/* <div className="graphAndResponse" style={{ display: displayAttribute }}> */}
              <div className="graphAndResponse">
                {extractResponse.visualization &&
                  extractResponse.visualization.responseType === "visual" &&
                  extractResponse.visualization.graphData?.length > 0 && (
                    <GraphVisualPlotly
                      visualization={{
                        graphType: extractResponse.visualization.graphType,
                        graphData: extractResponse.visualization.graphData,
                        responseType:
                          extractResponse.visualization.responseType,
                        label: extractResponse.visualization.question,
                        component: "dashboard",
                      }}
                    />
                  )}

                <div
                  className="responseInReportDashboard"
                  style={{
                    backgroundColor: "#f1f1f1",
                    // width: "fit-content",
                    // maxWidth: '60%',
                    minWwidth: "auto",
                    // width: displayAttribute ? '45%' : '100%',
                    marginBottom: "8px",
                    padding: "15px",
                    borderRadius: "8px",
                    lineHeight: 1.6,
                  }}
                >
                  <div className="response-container">
                    <ReactMarkdown>
                      {extractResponse.message.summary ||
                        FormatNonExcelResponse(extractResponse.message)}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            </Box>
          );
        })}
      </Box>
    </>
  );
};

const FormatNonExcelResponse = (response) => {
  return JSON.stringify(response).slice(1, -1).replace(/\\n/g, "\n");
};
