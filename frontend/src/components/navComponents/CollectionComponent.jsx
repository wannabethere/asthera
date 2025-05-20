import React, { useState, useRef, useEffect, useMemo, Component } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Tooltip,
  Typography,
  Button,
  Divider,
  Tabs,
  Avatar,
  FormControl,
  TextareaAutosize,
  Card,
  CardContent,
} from "@mui/material";
import { styled } from "@mui/material/styles";
import { HiMiniChevronDoubleLeft } from "react-icons/hi2";
import { LuChevronsRight } from "react-icons/lu";
import { IoMdAttach, IoIosSend } from "react-icons/io";
import { CiEdit } from "react-icons/ci";
import { IoMdCopy } from "react-icons/io";
import { BeatLoader } from "react-spinners";
import "../../css/sentBox.css";
import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule,
  ModuleRegistry,
  colorSchemeDarkBlue,
  themeQuartz,
} from "ag-grid-community";
import Plot from "react-plotly.js";
import Tab from "@mui/material/Tab";
import TabContext from "@mui/lab/TabContext";
import TabList from "@mui/lab/TabList";
import TabPanel from "@mui/lab/TabPanel";
import { FaFileAlt } from "react-icons/fa";
import { IoCloseCircleOutline } from "react-icons/io5";

import * as XLSX from "xlsx";
import { useConversation } from "../../context/ConversationContext";
import "../../css/navComponents/ThreadsComponent.css";
import { MdAddCircleOutline } from "react-icons/md";
import Snackbar from "@mui/material/Snackbar";
import Alert from "@mui/material/Alert";
import { GraphVisualPlotly } from "./GraphVisualPlotlyComponent";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";

import AccountCircleOutlinedIcon from "@mui/icons-material/AccountCircleOutlined";
import {
  BarChart as BarChartIcon,
  StackedBarChart as StackedBarChartIcon,
  ShowChart as ShowChartIcon,
  BubbleChart as ScatterPlotIcon,
  PieChart as PieChartIcon,
  Timeline as HistogramIcon,
  StackedLineChart as StackedAreaIcon,
  ShowChart as AxisIcon,
  TrendingUp,
} from "@mui/icons-material";
import { Select, MenuItem, InputLabel } from "@mui/material";
import StopCircleIcon from "@mui/icons-material/StopCircle";
import OutboundIcon from "@mui/icons-material/Outbound";
import AttachFileIcon from "@mui/icons-material/AttachFile";

const drawerWidth = 400;
const currentUser = JSON.parse(localStorage.getItem("currentUser"));

const openedMixin = (theme) => ({
  width: drawerWidth,
  transition: theme.transitions.create("width", {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.enteringScreen,
  }),
  overflowX: "hidden",
});

const closedMixin = (theme) => ({
  transition: theme.transitions.create("width", {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  overflowX: "hidden",
  width: 0,
});

styled("div")(({ theme, open }) => ({
  width: drawerWidth,
  position: "absolute",
  right: 0,
  top: 0,
  height: "100vh",
  transition: "width 0.3s ease-in-out",
  overflow: "hidden",
  ...(open ? openedMixin(theme) : closedMixin(theme)),
}));

export const CollectionComponent = ({
  threads,
  setThreads,
  currentThreadIndex,
  setCurrentThreadIndex,
}) => {
  const { conversations, setConversations } = useConversation();
  const [apiData, setApiData] = useState([]);
  const [activeNavTab, setActiveNavTab] = useState(0);
  const handleNavTabChange = (event, newValue) => {
    setActiveNavTab(newValue);
  };

  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const messageRefs = useRef([]);
  const fileInputRef = useRef(null);
  const [fileNameAndSize, setFileNameAndSize] = useState({
    fileName: "",
    fileSize: "",
    isFileExists: false,
  });
  const [completedFileDetails, setcompletedFileDetails] = useState({});
  const [agGridLoad, setAgGridLoad] = useState(false);
  const [isQuerySent, setIsQuerySent] = useState(false);
  const [globalValue, setGlobalValue] = useState(""); // Global user name Variable
  const [abortController, setAbortController] = useState(new AbortController());
  const navigate = useNavigate();

  useEffect(() => {
    const validMessages =
      threads?.[currentThreadIndex]?.messages?.filter(
        (msg) => msg.question?.trim() || msg.response?.trim()
      ) || [];
    setConversations(validMessages);
  }, [currentThreadIndex, threads]);

  useEffect(() => {
    messageRefs.current = messageRefs.current.slice(0, conversations.length);
  }, [conversations]);

  const handleOpenDialogPicker = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    setcompletedFileDetails({ file: e.target.files[0] });

    if (!file) return;
    setFileNameAndSize({
      fileName: file.name,
      fileSize: `${(file.size / 1024).toFixed(2)} KB`,
      isFileExists: true,
    });
  };

  const handleFileDiscard = () => {
    setFileNameAndSize({
      fileName: "",
      fileSize: "",
      isFileExists: false,
    });
    setcompletedFileDetails({});
  };

  const analyzeExcelData = async (file) => {
    try {
      const jsonData = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const data = new Uint8Array(e.target.result);
            const workbook = XLSX.read(data, { type: "array" });
            const jsonData = XLSX.utils.sheet_to_json(
              workbook.Sheets[workbook.SheetNames[0]]
            );
            resolve(jsonData);
          } catch (error) {
            reject(error);
          }
        };
        reader.onerror = reject;
        reader.readAsArrayBuffer(file);
      });

      return { excelJson: jsonData };
    } catch (error) {
      console.error("Error analyzing Excel data:", error);
      return { analysis: "Error analyzing the Excel file.", excelJson: [] };
    }
  };

  const handleSendMessage = async () => {
    const controller = new AbortController();
    setAbortController(controller);

    if (!inputValue.trim() && !fileNameAndSize?.isFileExists) {
      return;
    }

    setAgGridLoad(true);
    setIsQuerySent(true);
    setLoading(true);

    const extractFileName = completedFileDetails?.file?.name
      .split("_")
      .join("-");
    const userPrompt = inputValue.trim() || `summary-${extractFileName}`;
    const newConversation = {
      question: userPrompt,
      response: "",
      history: [],
      currentVersion: 0,
      isEdited: false,
      isFileUploaded: !!completedFileDetails?.file,
      fileName: completedFileDetails?.file?.name || "",
      fileSize: completedFileDetails?.file
        ? `${(completedFileDetails.file.size / 1024).toFixed(2)} KB`
        : "",
      excelData: [],
      text: userPrompt,
      sender: currentUser.email,
      visualGraphData: [],
    };

    const updated = [...conversations, newConversation];
    setConversations(updated);
    setInputValue("");

    try {
      let fullResponse;
      const currentThread = threads[currentThreadIndex] || {
        messages: [],
        sessionId: null,
      };
      let sessionId = currentThread.sessionId;
      let isNewSession = !sessionId; // If sessionId is null, it's a new session

      if (completedFileDetails?.file) {
        const { excelJson } = await analyzeExcelData(completedFileDetails.file);
        setAgGridLoad(false);

        const withExcel = [...updated];
        withExcel[withExcel.length - 1].excelData = excelJson;
        setConversations(withExcel);

        const excelPrompt = `
                You are answering questions about an Excel file. First provide a brief overview of the file, then answer the user's question. Here's the analysis you already did:
               ${JSON.stringify(excelJson.slice(0, 10), null, 2)}

                The user has asked:
                ${userPrompt}

                1. Key Trends
                2. Key columns and their purposes
                3. Data Issues
                4. Any Suggestions needed

                Additionally, provide 3 or 4 recommended analysis questions based on this data.
                `;

        const formData = new FormData();
        formData.append("user_input", excelPrompt);
        formData.append("owner_email", currentUser.email);
        formData.append("uploadedFiles", completedFileDetails.file);

        const endpoint = sessionId
          ? `/chat/${sessionId}/continue`
          : "/chat/start";
        const response = await fetch(`http://127.0.0.1:8000${endpoint}`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });

        const data = await response.json();
        setApiData(data);
        const parsedResponse = JSON.parse(data.response);

        let res = parsedResponse["summary"];

        fullResponse = updated.map((msg, i) =>
          i === updated.length - 1
            ? {
                ...msg,
                response: formatExcelUploadResponse(data),
                QuestionId: data.question_id,
                isEdited: false,
                visualGraphData: parsedResponse.graphData || [],
                graphType: parsedResponse.graphType || "",
                responseType: parsedResponse.responseType || "",
              }
            : msg
        );

        updateThread(fullResponse, sessionId || data.session_id);
      } else {
        const formData = new FormData();
        formData.append("user_input", userPrompt);
        formData.append("owner_email", currentUser.email);
        const endpoint = isNewSession
          ? "/chat/start"
          : `/chat/${sessionId}/continue`;
        const response = await fetch(`http://127.0.0.1:8000${endpoint}`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });

        const data = await response.json();
        setApiData(data);
        const parsedResponse = JSON.parse(data.response);

        let res = parsedResponse["summary"];

        fullResponse = updated.map((msg, i) =>
          i === updated.length - 1
            ? {
                ...msg,
                response: FormatNonExcelResponse(data),
                QuestionId: data.question_id,
                isEdited: false,
                visualGraphData: parsedResponse.graphData || [],
                graphType: parsedResponse.graphType || "",
                responseType: parsedResponse.responseType || "",
              }
            : msg
        );

        updateThread(fullResponse, sessionId || data.session_id);
      }
    } catch (error) {
      console.error("Error:", error);
      const errored = updated.map((msg, i) =>
        i === updated.length - 1 ? { ...msg, response: "Server is Busy." } : msg
      );
      setConversations(errored);
      updateThread(errored);
    }

    setLoading(false);
    setIsQuerySent(false);

    setFileNameAndSize({
      fileName: "",
      fileSize: "",
      isFileExists: false,
    });
    setcompletedFileDetails({});

    if (fileInputRef.current) {
      fileInputRef.current.value = null;
    }
  };

  const updateThread = (updatedMessages, newSessionId = null) => {
    const all = [...threads];
    const existingThread = all[currentThreadIndex] || {
      sessionId: null,
      messages: [],
      name: `Thread ${currentThreadIndex + 1}`,
      pinned: false,
    };

    all[currentThreadIndex] = {
      ...existingThread,
      messages: updatedMessages,
      sessionId: newSessionId || existingThread.sessionId,
      name: existingThread.name || `Thread ${currentThreadIndex + 1}`,
      pinned: existingThread.pinned || false,
      attachedFile: undefined,
    };

    setThreads(all);
  };

  const stopApiCall = () => {
    if (abortController) {
      abortController.abort();
      setAbortController(new AbortController());
    }
    setLoading(false);
    setIsQuerySent(false);
  };

  const scrollToMessage = (index) => {
    if (messageRefs.current[index]) {
      messageRefs.current[index].scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  };

  useEffect(() => {
    const currentThread = threads?.[currentThreadIndex];

    if (currentThread?.fileAttachment && !fileNameAndSize.isFileExists) {
      const attachedFile = currentThread.fileAttachment;

      setFileNameAndSize({
        fileName: attachedFile.filename,
        fileSize: attachedFile.fileSize,
        isFileExists: true,
      });

      fetch(
        `http://127.0.0.1:8000/uploadedfiles/${attachedFile.file_id}/download`
      )
        .then((res) => res.blob())
        .then((blob) => {
          const simulatedFile = new File([blob], attachedFile.filename);
          setcompletedFileDetails({ file: simulatedFile });
        })
        .catch((err) => {
          console.error("Failed to preload file:", err);
        });
    }
  }, [currentThreadIndex]);

  useEffect(() => {
    setGlobalValue(window.myGlobalVariable);
  }, []);

  return (
    <Box sx={{ display: "flex", height: "92vh" }}>
      <Box
        sx={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          height: "100%",
          position: "relative",
          marginTop: "15px",
        }}
      >
        {/* Scrollable chat content - Preserved your exact className */}
        <Box
          className="chatMessages"
          sx={{
            flex: 1,
            overflowY: "auto",
            padding: 2,
            paddingBottom: "100px",
            display: "flex",
            // justifyContent:'center',
            alignItems: "center",
          }}
        >
          {conversations.map((conversation, index) => (
            <div
              key={index}
              ref={(el) => (messageRefs.current[index] = el)}
              style={{ width: "85%", paddingTop: "39px" }}
            >
              <EditCopySave
                conversation={conversation}
                currentIndex={index}
                sessionId={threads[currentThreadIndex]?.sessionId}
                fileNameAndSize={fileNameAndSize}
                agGridLoad={agGridLoad}
                setConversations={setConversations}
                apiData={apiData}
              />
            </div>
          ))}
        </Box>

        {/* Fixed input box*/}
        <Box
          className="sentBox-container"
          sx={{
            bottom: 0,
            width: "80%",
            backgroundColor: "#fff",
            borderTop: "1px solid #ddd",
            padding: 2,
            display: "flex",
            alignItems: "center",
            gap: 1,
          }}
        >
          <Box>
            {fileNameAndSize.isFileExists && (
              <Box
                className="upload-file-container"
                sx={{
                  display: `${isQuerySent ? "none" : "flex"}`,
                  borderRadius: "20px",
                }}
              >
                <Box className="file-icon">
                  <FaFileAlt />
                </Box>
                <Box sx={{ margin: "8px" }}>
                  <Typography>{fileNameAndSize.fileName}</Typography>
                  <Typography>{fileNameAndSize.fileSize}</Typography>
                </Box>
                <IoCloseCircleOutline onClick={handleFileDiscard} />
              </Box>
            )}
          </Box>

          <Box
            className="sentBox-container_text"
            sx={{
              display: "flex",
              alignItems: "center",
            }}
          >
            {/* Attach File Button */}
            <IconButton
              color="primary"
              onClick={handleOpenDialogPicker}
              disabled={loading}
              sx={{
                p: 1.8,
                transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                backgroundColor: "rgba(25, 118, 210, 0.08)",
                "&:hover": {
                  backgroundColor: "rgba(25, 118, 210, 0.15)",
                  transform: "scale(1.1)",
                },
                "&:active": {
                  transform: "scale(0.95)",
                },
                "&:disabled": {
                  backgroundColor: "rgba(0, 0, 0, 0.02)",
                  color: "rgba(0, 0, 0, 0.26)",
                  transform: "none",
                },
                "& .MuiTouchRipple-root": {
                  color: "primary.main",
                },
              }}
            >
              <AttachFileIcon
                fontSize="1.2rem"
                sx={{
                  transition: "transform 0.2s",
                  "&:hover": {
                    transform: "rotate(-15deg)",
                  },
                }}
              />
            </IconButton>

            {/* Hidden file input */}
            <input
              type="file"
              accept=".xlsx, .xls, .csv"
              ref={fileInputRef}
              onChange={handleFileUpload}
              style={{ display: "none" }}
              disabled={loading}
            />

            {/* Message Textarea */}
            <Box
              sx={{
                flex: 1,
                position: "relative",
              }}
            >
              <TextareaAutosize
                minRows={1}
                maxRows={6}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (!loading) {
                      // Only send if not loading
                      handleSendMessage();
                    }
                  }
                }}
                placeholder="Ask anything..."
                // disabled={loading}
                style={{
                  width: "100%",
                  border: "none",
                  borderRadius: "24px",
                  padding: "12px 48px 12px 16px",
                  fontSize: "0.875rem",
                  resize: "none",
                  backgroundColor: "transparent",
                  outline: "none",
                  fontFamily: "inherit",
                  lineHeight: 1.5,
                  opacity: loading ? 0.7 : 1,
                }}
              />
            </Box>

            {/* Send/Stop Button */}
            <IconButton
              onClick={loading ? stopApiCall : handleSendMessage}
              disabled={
                !inputValue.trim() && !fileNameAndSize?.isFileExists && !loading
              }
              sx={{
                p: 0,
                mx: 1,
                color: loading ? "error.main" : "black",
                "&:hover": {
                  backgroundColor: "transparent",
                  color: loading ? "error.dark" : "primary.dark",
                },
                "&:disabled": {
                  color: "action.disabled",
                },
                transition: "all 0.2s ease",
              }}
            >
              {loading ? (
                <StopCircleIcon sx={{ fontSize: "41px" }} />
              ) : (
                <OutboundIcon sx={{ fontSize: "41px" }} />
              )}
            </IconButton>
          </Box>
        </Box>
      </Box>

      {/* History sidebar - Preserved your exact styling */}
      <Box
        sx={{
          width: historyOpen ? drawerWidth : 0,
          transition: "width 0.3s ease-in-out",
          overflow: "hidden",
        }}
      >
        <Box
          sx={{ p: 2, mt: 4, borderLeft: "1px solid #e5e5e5" }}
          className="SideNavtab"
        >
          <Tabs
            value={activeNavTab}
            onChange={handleNavTabChange}
            variant="fullWidth"
            sx={{
              minHeight: "40px",
              "& .MuiTabs-indicator": {
                display: "none", //  removes the underline
              },
              "& .MuiTab-root": {
                textTransform: "none",
                minHeight: "40px",
                fontSize: "17px",
                fontFamily: "'IBM Plex Sans', system-ui, sans-serif !important",
              },
              "& .MuiTabs-list": {
                color: (theme) =>
                  theme.palette.mode === "dark"
                    ? "rgb(237 236 236 / 74%)"
                    : "black",
                backgroundColor: (theme) =>
                  theme.palette.mode === "dark" ? "#424242" : "#F2F1F1",
                borderRadius: "9px",
              },
              "& .Mui-selected": {
                color: (theme) =>
                  theme.palette.mode === "dark"
                    ? "rgb(237 236 236 / 74%) !important"
                    : "#000 !important",
                backgroundColor: (theme) =>
                  theme.palette.mode === "dark" ? "#575757" : "white",
                border: (theme) =>
                  theme.palette.mode === "dark"
                    ? "1px solid #818181"
                    : "1px solid #e6e6e6",
                borderRadius: "9px",
              },
            }}
          >
            <Tab label="Overview" />
            <Tab label="Notes" />
            <Tab label="Reasoning" />
          </Tabs>

          <Box sx={{ mt: 2, height: "calc(100vh - 120px)", overflowY: "auto" }}>
            {activeNavTab === 0 && (
              <>
                {conversations.length > 0 ? (
                  <List>
                    {conversations
                      // .filter((msg) => msg.sender === "user")
                      .map((msg, idx) => (
                        <ListItem
                          key={idx}
                          onClick={() => scrollToMessage(idx)}
                        >
                          <ListItemText
                            primary={
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  backgroundColor: (theme) =>
                                    theme.palette.mode === "dark"
                                      ? "#424242"
                                      : "#f4f4f4",
                                  color: (theme) =>
                                    theme.palette.mode === "dark"
                                      ? "rgb(237 236 236 / 74%)"
                                      : "#000",
                                  width: "fit-content",
                                  padding: "5px 12px",
                                  borderRadius: "9px",
                                  cursor: "pointer",
                                }}
                              >
                                <IconButton
                                  size="small"
                                  sx={{
                                    m: 0,
                                    p: 0,
                                    pr: 1,
                                    "&:hover": {
                                      backgroundColor: "transparent",
                                    },
                                  }}
                                >
                                  <Avatar
                                    sx={{
                                      width: 24,
                                      height: 24,
                                      fontSize: "12px",
                                    }}
                                  >
                                    {msg.sender[0].toUpperCase()}
                                  </Avatar>
                                </IconButton>
                                {msg.text}
                              </Box>
                            }
                          />
                        </ListItem>
                      ))}
                  </List>
                ) : (
                  <Typography
                    variant="body2"
                    sx={{
                      mx: 1,
                      color: (theme) =>
                        theme.palette.mode === "dark"
                          ? "rgb(237 236 236 / 74%)"
                          : "#000",
                    }}
                  >
                    No history for this thread.
                  </Typography>
                )}
              </>
            )}

            {activeNavTab === 1 && (
              <>
                <Button
                  sx={{
                    mx: 1,
                    color: (theme) =>
                      theme.palette.mode === "dark"
                        ? "rgb(237 236 236 / 74%)"
                        : "#000",
                  }}
                  className="viewReportButton"
                  variant="h5"
                  onClick={() => navigate("/report-dashboard")}
                >
                  Click here to view the reports
                </Button>
              </>
            )}

            {activeNavTab === 2 && (
              <>
                <Typography
                  variant="h6"
                  sx={{
                    mx: 1,
                    color: (theme) =>
                      theme.palette.mode === "dark"
                        ? "rgb(237 236 236 / 74%)"
                        : "#000",
                  }}
                  gutterBottom
                >
                  Reasoning
                </Typography>
              </>
            )}
          </Box>
        </Box>
      </Box>

      <Tooltip title={historyOpen ? "Close History" : "Show History"}>
        <IconButton
          onClick={() => setHistoryOpen(!historyOpen)}
          sx={{
            position: "fixed",
            top: "50%",
            right: historyOpen ? `${drawerWidth + 35}px` : "10px",
            transform: "translateY(-50%)",
            transition: "right 0.3s ease-in-out",
            backgroundColor: (theme) =>
              theme.palette.mode === "dark" ? "#333" : "#fff",
            borderRadius: "50%",
            boxShadow: "0px 4px 6px rgba(0,0,0,0.1)",
            zIndex: 1300,
            animation: !historyOpen ? "blinkAnimation 1s infinite" : "none", // Apply blink animation conditionally
            border: (theme) =>
              theme.palette.mode === "dark"
                ? "2px solid rgb(135 135 135 / 70%) !important" // Dark mode border
                : "2px solid #e5e5e5 !important", // Light mode border
            "&:hover": {
              backgroundColor: (theme) =>
                theme.palette.mode === "dark" ? "#444" : "#f1f1f1",
            },
          }}
        >
          {historyOpen ? <LuChevronsRight /> : <HiMiniChevronDoubleLeft />}
        </IconButton>
      </Tooltip>
    </Box>
  );
};

const EditCopySave = ({
  conversation,
  setConversations,
  currentIndex,
  updateThread,
  sessionId,
  agGridLoad,
  apiData,
}) => {
  const [tabValue, setTabValue] = useState("1");
  const [isCopied, setIsCopied] = useState(false);
  const [isEdit, setIsEdit] = useState(false);
  const [editValue, setEditValue] = useState(conversation.question);
  const [colDefs, setColDefs] = useState([]);
  const [uploadToReport, setUploadReport] = useState();
  const [openSnackBar, setOpenSnackBar] = React.useState(false);

  ModuleRegistry.registerModules([AllCommunityModule]);
  const myTheme = themeQuartz.withParams({
    headerFontFamily: '"IBM Plex Sans", system-ui, sans-serif !important',
    cellFontFamily: '"IBM Plex Sans", system-ui, sans-serif !important',
    wrapperBorder: true,
    headerRowBorder: true,
    // headerColumnBorder:true,
    rowBorder: { style: "solid", width: 1, color: "#ededed" },
    columnBorder: { style: "solid", color: "#ededed" },
  });

  const rowSelection = useMemo(() => {
    return {
      mode: "multiRow",
    };
  }, []);

  const generateColumnDefs = (data) => {
    if (!data || data.length === 0) return [];

    const headers = Object.keys(data[0]);
    return headers.map((header) => ({
      field: header,
      headerName: header.toUpperCase().replace(/_/g, " "),
      sortable: true,
      filter: true,
      editable: true,
    }));
  };

  useEffect(() => {
    if (
      Array.isArray(conversation?.excelData) &&
      conversation.excelData.length > 0
    ) {
      const newColDefs = generateColumnDefs(conversation.excelData);
      setColDefs(newColDefs);
    } else {
      setColDefs([]);
    }
  }, [conversation.excelData]);

  const handleTabListChange = (event, newValue) => {
    setTabValue(newValue);
  };

  const handleCopy = () => {
    navigator.clipboard
      .writeText(conversation.question || "")
      .then(() => {
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
      })
      .catch(console.error);
  };
  const handleResponseCopy = () => {
    navigator.clipboard
      .writeText(conversation.response || "")
      .then(() => {
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
      })
      .catch(console.error);
  };

  const handleEdit = () => {
    setIsEdit(true);
    setEditValue(conversation.question);
  };

  const handleUpdateText = async () => {
    if (!editValue.trim()) return;

    const newHistory = [
      {
        question: conversation.question,
        response: conversation.response,
        timestamp: new Date().toISOString(),
      },
      ...(conversation.history || []),
    ];

    setConversations((prev) => {
      const updated = [...prev];
      updated[currentIndex] = {
        ...updated[currentIndex],
        question: editValue,
        text: editValue,
        response: "",
        history: newHistory,
        currentVersion: 0,
        isEdited: true,
      };
      updateThread(updated);
      return updated;
    });

    try {
      const formData = new FormData();
      formData.append("user_input", editValue);
      formData.append("owner_email", currentUser.email);
      if (conversation.QuestionId) {
        formData.append("question_id", conversation.QuestionId);
        console.log("Sending question_id:", conversation.QuestionId);
      } else {
        console.warn(
          "No QuestionId found — this will be treated as a new message"
        );
      }
      const response = await fetch(
        `http://127.0.0.1:8000/chat/${sessionId}/continue`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();
      console.log("Server responded with updated response:", data);

      setConversations((prev) => {
        const updated = [...prev];
        updated[currentIndex] = {
          ...updated[currentIndex],
          response: FormatAIResponse(data.response),
          QuestionId: data.question_id,
          isEdited: true,
        };
        updateThread(updated);
        console.log("Updated Conversations State:", updated);
        return updated;
      });
    } catch (error) {
      console.error("Error:", error);
      setConversations((prev) => {
        const updated = [...prev];
        updated[currentIndex].response = "Error fetching response.";
        updateThread(updated);
        return updated;
      });
    }

    setIsEdit(false);
  };

  const handleCancel = () => {
    setIsEdit(false);
    setEditValue(conversation.question);
  };

  const handleVersionChange = (direction) => {
    setConversations((prev) => {
      const updated = [...prev];
      const conv = updated[currentIndex];
      const newVer = conv.currentVersion + direction;
      if (newVer >= 0 && newVer <= (conv.history?.length || 0)) {
        conv.currentVersion = newVer;
      }
      updateThread(updated);
      return updated;
    });
  };

  const getCurrentVersion = () => {
    if (
      !conversation.history ||
      conversation.history.length === 0 ||
      conversation.currentVersion === 0
    ) {
      return {
        question: conversation.question,
        sender: conversation.sender,
        response:
          conversation.response.responseType === "unrelated"
            ? FormatUnreleatedThreadResponse(conversation)
            : FormatThreadResponse(conversation),
        convo: conversation,
      };
    }

    return conversation.history[conversation.currentVersion - 1];
  };

  const currentData = getCurrentVersion();
  const showVersionControls =
    conversation.isEdited && (conversation.history?.length || 0) > 0;

  const addToReport = async (conversation) => {
    const bodyData = {
      questionId: conversation.QuestionId,
      questionName: conversation.question,
      sessionId: sessionId,
      addedDate: new Date().toISOString(),
      response: {
        res: {
          message: conversation.response,
          visualization: {
            graphType: conversation.graphType,
            graphData: conversation.visualGraphData,
            responseType: conversation.responseType,
            label: conversation.question,
          },
        },
      },
    };

    try {
      const res = await fetch(`http://127.0.0.1:8000/chat/add-chats/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bodyData),
      });

      const json = await res.json();
      console.log("Response from API:", json);
    } catch (error) {
      console.error("Error adding to report:", error);
    }
  };

  const handleClickSnackBar = () => {
    setOpenSnackBar(true);
  };

  const handleCloseSnackBar = (event, reason) => {
    if (reason === "clickaway") {
      return;
    }

    setOpenSnackBar(false);
  };

  return (
    <>
      {/* User Question (right side) */}
      <div
        style={{
          textAlign: "right",
          fontSize: "0.8em",
          fontFamily: "system-ui",
        }}
      >
        {currentData.sender}
      </div>
      <div
        className="chateachMessage"
        style={{
          // backgroundColor: "#daf8cb",
          backgroundColor: "#f1f1f1",
          maxWidth: isEdit ? "60%" : "80%",
          minWidth: isEdit ? "60%" : "auto",
          width: "fit-content",
          marginLeft: "auto",
          marginBottom: "8px",
        }}
      >
        {isEdit ? (
          <>
            <textarea
              className="textareaField"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              style={{ width: "100%", minHeight: "60px" }}
            />
            <Box style={{ display: "flex", gap: "10px", marginTop: "5px" }}>
              <Button
                onClick={handleUpdateText}
                variant="contained"
                style={{ backgroundColor: "#4CAF50", color: "white" }}
              >
                Update
              </Button>
              <Button
                onClick={handleCancel}
                variant="contained"
                style={{ backgroundColor: "#f44336", color: "white" }}
              >
                Cancel
              </Button>
            </Box>
          </>
        ) : (
          <div className="question">
            {conversation.isFileUploaded && (
              <Box
                className="upload-file-container"
                sx={{ display: "flex", borderRadius: "20px" }}
              >
                <Box className="file-icon">
                  <FaFileAlt />
                </Box>
                <Box sx={{ margin: "8px" }}>
                  <Typography>{conversation.fileName}</Typography>
                  <Typography>{conversation.fileSize}</Typography>
                </Box>
              </Box>
            )}
            {currentData.question}
            {showVersionControls && (
              <div
                style={{ fontSize: "12px", color: "gray", marginTop: "5px" }}
              >
                <button
                  onClick={() => handleVersionChange(-1)}
                  disabled={conversation.currentVersion === 0}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  ◀️
                </button>
                <span style={{ margin: "0 8px" }}>
                  {conversation.currentVersion + 1} /{" "}
                  {(conversation.history?.length || 0) + 1}
                </span>
                <button
                  onClick={() => handleVersionChange(1)}
                  disabled={
                    conversation.currentVersion ===
                    (conversation.history?.length || 0)
                  }
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  ▶️
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Action buttons (right side with question) */}
      <Box
        style={{
          alignSelf: "flex-end",
          display: "flex",
          gap: "10px",
          marginBottom: "8px",
          justifyContent: "flex-end",
        }}
      >
        <CiEdit
          onClick={handleEdit}
          style={{ cursor: "pointer", fontSize: "20px" }}
          title="Edit question"
        />
        <Tooltip title={isCopied ? "Copied!" : "Copy"} placement="bottom">
          <IoMdCopy
            onClick={handleCopy}
            style={{
              cursor: "pointer",
              color: isCopied ? "green" : "black",
              fontSize: "20px",
            }}
          />
        </Tooltip>
      </Box>

      {/* Bot Response (left side) */}
      {conversation.isFileUploaded && (
        <TabContext value={tabValue}>
          <Box>
            <TabList
              indicatorColor="none"
              textColor="inherit"
              onChange={handleTabListChange}
              className="TabListCollection"
            >
              <Tab
                sx={{ border: 1, borderColor: "divider" }}
                className="TabCollection"
                label="Table"
                value="1"
              />
              <Tab
                sx={{ border: 1, borderColor: "divider" }}
                className="TabCollection"
                label="Chart"
                value="2"
              />
            </TabList>
          </Box>

          <TabPanel className="TabPanelHome" value="1">
            {conversation.isFileUploaded && (
              <div
                style={{
                  width: "100%",
                  marginBottom: "20px",
                  height: "fit-content",
                }}
              >
                <AgGridReact
                  className="ag-theme-quartz"
                  theme={myTheme}
                  rowSelection={rowSelection}
                  rowData={conversation.excelData}
                  columnDefs={colDefs}
                  defaultColDef={{
                    sortable: true,
                    filter: true,
                    editable: false,
                    // flex: 1,
                    // minWidth: 80,
                    // maxWidth: 300,
                  }}
                  // Pagination properties
                  pagination={true}
                  paginationPageSize={10}
                  domLayout="autoHeight"
                  headerHeight={40}
                  rowHeight={35}
                  suppressScrollOnNewData={true}
                  suppressCellFocus={true}
                  suppressClickEdit={true} // Prevents editing on clicks
                  singleClickEdit={false} // Requires double-click to edit (extra safety)
                  stopEditingWhenCellsLoseFocus={true}
                />
              </div>
            )}
          </TabPanel>

          <TabPanel
            className="TabPanelHome"
            value="2"
            sx={{ width: "100%", borderRadius: "10px" }}
          >
            {conversation.isFileUploaded && (
              <GraphPlotlyUI conversation={conversation} />
            )}
          </TabPanel>
        </TabContext>
      )}

      {!currentData.response ? (
        <BeatLoader size={10} />
      ) : (
        <>
          <Tooltip placeholder="top" title="Add to reports">
            <Button
              onClick={handleClickSnackBar}
              sx={{ justifyContent: "start" }}
            >
              <MdAddCircleOutline
                className="addToreport"
                sx={{ fontSize: "1.3rem" }}
                onClick={() => addToReport(conversation)}
              />
            </Button>
            <Snackbar
              open={openSnackBar}
              autoHideDuration={6000}
              onClose={handleCloseSnackBar}
            >
              <Alert
                onClose={handleCloseSnackBar}
                severity="success"
                variant="filled"
                sx={{ width: "100%" }}
              >
                Response Succesfully added into Reports.!!
              </Alert>
            </Snackbar>
          </Tooltip>

          {!conversation.isFileUploaded &&
            conversation.responseType === "visual" &&
            conversation.visualGraphData?.length > 0 && (
              <GraphVisualPlotly
                visualization={{
                  graphType: conversation.graphType,
                  graphData: conversation.visualGraphData,
                  responseType: conversation.responseType,
                  label: conversation.question,
                  component: "collection",
                }}
              />
            )}

          <div
            className="chateachMessage"
            style={{
              // backgroundColor: "#f1f1f1",
              maxWidth: isEdit ? "60%" : "80%",
              minWidth: isEdit ? "60%" : "auto",
              width: "fit-content",
              marginBottom: "8px",
              padding: "10px",
              borderRadius: "8px",
              lineHeight: 1.6,
            }}
          >
            <div className="response-container">
              <ReactMarkdown>{currentData.response}</ReactMarkdown>
            </div>
          </div>

          <Box
            style={{
              alignSelf: "flex-start",
              display: "flex",
              gap: "10px",
              marginBottom: "8px",
              justifyContent: "flex-start",
            }}
          >
            <Tooltip title={isCopied ? "Copied!" : "Copy"} placement="bottom">
              <IoMdCopy
                onClick={handleResponseCopy}
                style={{
                  cursor: "pointer",
                  color: isCopied ? "green" : "black",
                  fontSize: "20px",
                }}
              />
            </Tooltip>
          </Box>
        </>
      )}
    </>
  );
};

const formatExcelUploadResponse = (text) => {
  console.log("1139-->formatExcelUploadResponse");
  if (!text) return "";

  let response = text.response;
  try {
    const outerParsed = JSON.parse(response); // <-- not parsed, use data

    if (outerParsed.responseType === "Summary" && outerParsed.summary) {
      let summaryParsed = outerParsed.summary;

      if (
        typeof summaryParsed === "string" &&
        summaryParsed.trim().startsWith("{")
      ) {
        try {
          summaryParsed = JSON.parse(summaryParsed);
        } catch (innerError) {
          console.warn(
            "Summary parsing failed. Trying to extract manually.",
            innerError
          );

          // ✨ Manual extraction if parsing fails
          const overviewMatch = summaryParsed.match(
            /"overview"\s*:\s*"([^"]*)"/
          );
          const keyInsightsMatch = summaryParsed.match(
            /"key_insights"\s*:\s*"([^"]*)"/
          );
          const predictionsMatch = summaryParsed.match(
            /"predictions"\s*:\s*"([^"]*)"/
          );

          const recommendedQuestionsMatch = summaryParsed.match(
            /"recommended_questions"\s*:\s*\[([^\]]*)\]/
          );

          let recommendedQuestions = [];
          if (recommendedQuestionsMatch && recommendedQuestionsMatch[1]) {
            recommendedQuestions = recommendedQuestionsMatch[1]
              .split(",")
              .map((q) => q.trim().replace(/^"|"$/g, "")); // remove quotes
          }

          return `
**Overview:**
${overviewMatch ? overviewMatch[1] : "No overview available."}
 
**Key Insights:**
${keyInsightsMatch ? keyInsightsMatch[1] : "No key insights available."}
 
**Predictions:**
${predictionsMatch ? predictionsMatch[1] : "No predictions available."}
 
**Recommended Questions:**
${
  recommendedQuestions.length
    ? recommendedQuestions.map((q, idx) => `${idx + 1}. ${q}`).join("\n")
    : "No recommended questions."
}
          `;
        }
      }

      return `
**Overview:**
${summaryParsed.overview || "No overview available."}
 
**Key Insights:**
${summaryParsed.key_insights || "No key insights available."}
 
**KPIs:**
${Object.entries(summaryParsed.kpis || {})
  .map(([key, value]) => `- ${key}: ${value}`)
  .join("\n")}
 
**Predictions:**
${summaryParsed.predictions || "No predictions available."}
 
**Recommended Questions:**
${summaryParsed.recommended_questions
  ?.map((q, idx) => `${idx + 1}. ${q}`)
  .join("\n")}
    `;
    }
  } catch (e) {
    console.error("Failed parsing response or summary", e);
  }
};

const FormatNonExcelResponse = (data) => {
  console.log("1212-->FormatNonExcelResponse");
  let parsingResponse;
  try {
    parsingResponse = JSON.parse(data.response);
  } catch (e) {
    parsingResponse = null;
  }

  if (parsingResponse?.responseType === "Summary") {
    return (data = formatExcelUploadResponse(data));
  } else if (parsingResponse?.responseType === "unrelated") {
    return (data = parsingResponse.summary.replace(/\\n/g, "\n"));
  } else if (parsingResponse?.responseType === "visual") {
    let summaryText = parsingResponse.summary.replace(/\\n/g, "\n");
    return (data = summaryText);
  } else if (parsingResponse?.responseType === "maths") {
    let summaryData = parsingResponse.summary;

    if (typeof summaryData === "string" && summaryData.trim().startsWith("{")) {
      try {
        summaryData = JSON.parse(summaryData);
      } catch (e) {
        console.error("Failed to parse maths summary", e);
      }
    }
    return (data = summaryData.summary);
    //   data = `
    // **Summary:**
    // ${summaryData.summary || "No summary available."}
    //   `;
  }
  // else if(parsedResponse?.responseType === "Summary" && ){

  // }
  else {
    return (data = data.response.slice(1, -1).replace(/\\n/g, "\n"));
  }
};

const formatExcelUploadThreadResponse = (text) => {
  console.log("1255-->formatExcelUploadThreadResponse");
  if (!text || !text.response) return "No response data provided.";

  const response = text.response;

  try {
    // Only handle summary responses
    if (response.responseType === "Summary" && response.summary) {
      let summaryParsed = response.summary;

      // Try to parse JSON string if needed
      if (
        typeof summaryParsed === "string" &&
        summaryParsed.trim().startsWith("{")
      ) {
        try {
          summaryParsed = JSON.parse(summaryParsed);
        } catch (parseError) {
          console.warn(
            "JSON parse failed. Proceeding with manual parsing.",
            parseError
          );
        }
      }

      // Manual extraction fallback if still a string
      if (typeof summaryParsed === "string") {
        const overviewMatch = summaryParsed.match(/"overview"\s*:\s*"([^"]*)"/);
        const keyInsightsMatch = summaryParsed.match(
          /"key_insights"\s*:\s*"([^"]*)"/
        );
        const predictionsMatch = summaryParsed.match(
          /"predictions"\s*:\s*"([^"]*)"/
        );
        const recommendedQuestionsMatch = summaryParsed.match(
          /"recommended_questions"\s*:\s*\[([^\]]*)\]/
        );

        let recommendedQuestions = [];
        if (recommendedQuestionsMatch && recommendedQuestionsMatch[1]) {
          recommendedQuestions = recommendedQuestionsMatch[1]
            .split(",")
            .map((q) => {
              if (q && typeof q === "string") {
                return q.trim().replace(/^"|"$/g, "");
              }
              return "";
            });
        }

        return `
**Overview:**
${overviewMatch ? overviewMatch[1] : "No overview available."}

**Key Insights:**
${keyInsightsMatch ? keyInsightsMatch[1] : "No key insights available."}

**Predictions:**
${predictionsMatch ? predictionsMatch[1] : "No predictions available."}

**Recommended Questions:**
${
  recommendedQuestions.length
    ? recommendedQuestions.map((q, idx) => `${idx + 1}. ${q}`).join("\n")
    : "No recommended questions available."
}
        `;
      }

      // If summaryParsed is a valid object
      if (typeof summaryParsed === "object") {
        return `
**Overview:**
${summaryParsed.overview || "No overview available."}

**Key Insights:**
${summaryParsed.key_insights || "No key insights available."}

**KPIs:**
${
  summaryParsed.kpis
    ? Object.entries(summaryParsed.kpis)
        .map(([key, value]) => `- ${key}: ${value}`)
        .join("\n")
    : "No KPIs available."
}

**Predictions:**
${summaryParsed.predictions || "No predictions available."}

**Recommended Questions:**
${
  summaryParsed.recommended_questions
    ? summaryParsed.recommended_questions
        .map((q, idx) => `${idx + 1}. ${q}`)
        .join("\n")
    : "No recommended questions available."
}
        `;
      }
    }
  } catch (error) {
    console.error("Error formatting AI response:", error);
    return "An error occurred while formatting the response.";
  }

  return "No valid summary found in the response.";
};

const FormatThreadResponse = (data) => {
  console.log("1343-->FormatThreadResponse");
  let parsingResponse = data.response.summary;

  if (data.response.responseType === "Summary") {
    return (data = formatExcelUploadThreadResponse(data));
  } else if (data.response.responseType === "unrelated") {
    return (data = parsingResponse.replace(/\\n/g, "\n"));
  } else if (data.response.responseType === "visual") {
    let summaryText = parsingResponse.replace(/\\n/g, "\n");
    return (data = summaryText);
  } else if (data.response.responseType === "maths") {
    let summaryData = parsingResponse;

    if (typeof summaryData === "string" && summaryData.trim().startsWith("{")) {
      try {
        summaryData = JSON.parse(summaryData);
      } catch (e) {
        console.error("Failed to parse maths summary", e);
      }
    }
    return (data = summaryData.summary);
  } else {
    // return data = data.response.slice(1, -1).replace(/\\n/g, "\n");
    return (data = data.response.replace(/\\n/g, "\n"));
  }
};

const FormatUnreleatedThreadResponse = (data) => {
  console.log("1375-->FormatUnreleatedThreadResponse");
  return JSON.stringify(data.response.summary)
    .slice(1, -1)
    .replace(/\\n/g, "\n");
};

const FormatAIResponse = (text) => {
  if (!text) return "";
  const text1 = text.responseType ? text.summary : text;
  return text1
    .replace(/</g, "&lt;") // sanitize any HTML
    .replace(/>/g, "&gt;")
    .replace(/\n{2,}/g, "\n") // collapse multiple newlines
    .replace(/\n/g, "<br>") // convert newlines to <br>
    .replace(/^\d+\.\s/gm, (match) => `<br><strong>${match.trim()}</strong>`) // highlight numbered items
    .replace(/(?<=\\s)-\\s/g, "<br>• "); // handle bullets
};

const GraphPlotlyUI = ({ conversation }) => {
  const [tabValue, setTabValue] = useState("1");
  const [graphType, setGraphType] = useState("bar");
  const [barMode, setBarMode] = useState(null);
  const [orientation, setOreintation] = useState("");
  const [mode, setMode] = useState("");
  const [fill, setFill] = useState("");
  const [selectValue, setSelectValue] = useState("scatter");

  // x-axis
  const [xaxisColumn, setXaxisColumn] = useState("Order ID");

  // y-axis
  const [yaxisColoumn, setYaxisColoumn] = useState("Customer ID");

  const chartOptions = [
    {
      value: "bar_group_coloumn",
      label: "Grouped Column",
      graphType: "bar",
      barMode: "group",
      orientation: "",
    },
    {
      value: "bar_stacked_coloumn",
      label: "Stacked Column",
      graphType: "bar",
      barMode: "stack",
      orientation: "",
    },
    {
      value: "scatter_multiple_line_chart",
      label: "Line Chart",
      graphType: "scatter",
      fill: "",
      mode: "lines+markers",
    },
    {
      value: "scatter_area_line_chart",
      label: "Stacked Area",
      graphType: "scatter",
      fill: "tozeroy",
      mode: "lines+markers",
    },
    {
      value: "scatter_markers_line_chart",
      label: "Scattered Plot",
      graphType: "scatter",
      fill: "",
      mode: "markers",
    },
    {
      value: "bar_group",
      label: "Grouped Bar",
      graphType: "bar",
      barMode: "group",
      orientation: "h",
    },
    {
      value: "bar_stacked",
      label: "Stacked Bar",
      graphType: "bar",
      barMode: "stack",
      orientation: "h",
    },
    {
      value: "histogram",
      label: "Histogram Bar",
      graphType: "histogram",
    },
    {
      value: "pie",
      label: "Pie Chart",
      graphType: "pie",
    },
  ];

  const handleGraphTypeChange = (event) => {
    const selectedValue = event.target.value;
    const selectedOption = chartOptions.find(
      (opt) => opt.value === selectedValue
    );

    if (!selectedOption) {
      console.warn("No config found for:", selectedValue);
      setSelectValue(selectedValue);
      setGraphType(null);
      setBarMode(null);
      setOreintation(null);
      setFill(null);
      setMode(null);
      return;
    }

    setSelectValue(selectedValue);
    setGraphType(selectedOption.graphType);

    if (selectedOption.graphType === "bar") {
      setBarMode(selectedOption.barMode || null);
      setOreintation(selectedOption.orientation || null);
      setFill(null);
      setMode(null);
    } else if (selectedOption.graphType === "scatter") {
      setFill(selectedOption.fill || null);
      setMode(selectedOption.mode || null);
      setBarMode(null);
      setOreintation(null);
    } else {
      setBarMode(null);
      setOreintation(null);
      setFill(null);
      setMode(null);
    }
  };

  return (
    <>
      <div style={{ width: "100%", height: 460, border: "1px solid #dfdada" }}>
        <Box sx={{ display: "flex", height: "100%" }}>
          <Box
            sx={{
              width: "30%",
              marginTop: "2%",
              marginLeft: "1%",
              minWidth: "335px",
              mr: "10px",
            }}
          >
            <Box
              sx={{
                position: "relative",
                minWidth: 240,
                mb: 2,
              }}
            >
              <InputLabel
                htmlFor="graphType"
                sx={{
                  position: "absolute",
                  top: -8,
                  left: 14,
                  px: 1,
                  bgcolor: "background.paper",
                  color: "text.secondary",
                  fontSize: "0.875rem",
                  zIndex: 1,
                }}
              >
                Type
              </InputLabel>
              <Select
                id="graphType"
                value={selectValue}
                onChange={handleGraphTypeChange}
                fullWidth
                sx={{
                  backgroundColor: "background.paper",
                  borderRadius: 2,
                  border: "1px solid",
                  borderColor: "divider",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.05)",
                  "&:hover": {
                    borderColor: "primary.main",
                  },
                  "& .MuiSelect-select": {
                    py: 1.5,
                    px: 2,
                  },
                }}
                MenuProps={{
                  PaperProps: {
                    sx: {
                      mt: 1,
                      boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                      borderRadius: 2,
                      "& .MuiMenuItem-root": {
                        py: 1.5,
                        px: 2,
                      },
                    },
                  },
                }}
              >
                <MenuItem
                  value="bar_group_coloumn"
                  data-barmode="group"
                  data-orientation=""
                  sx={{ borderBottom: "1px solid", borderColor: "divider" }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <BarChartIcon sx={{ color: "primary.main" }} />
                    <span>Grouped Coloumn</span>
                  </Box>
                </MenuItem>

                <MenuItem
                  value="bar_stacked_coloumn"
                  data-barmode="stack"
                  data-orientation=""
                  sx={{ borderBottom: "1px solid", borderColor: "divider" }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <StackedBarChartIcon sx={{ color: "primary.main" }} />
                    <span>Stacked Coloumn</span>
                  </Box>
                </MenuItem>

                <MenuItem
                  value="scatter_multiple_line_chart"
                  data-fill=""
                  data-mode="lines+markers"
                  sx={{ borderBottom: "1px solid", borderColor: "divider" }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <ShowChartIcon sx={{ color: "primary.main" }} />
                    <span>Line Chart</span>
                  </Box>
                </MenuItem>

                <MenuItem
                  value="scatter_area_line_chart"
                  data-fill="tozeroy"
                  data-mode="lines+markers"
                  sx={{ borderBottom: "1px solid", borderColor: "divider" }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <StackedAreaIcon sx={{ color: "primary.main" }} />
                    <span>Stacked Area</span>
                  </Box>
                </MenuItem>

                <MenuItem
                  value="scatter_markers_line_chart"
                  data-fill=""
                  data-mode="markers"
                  sx={{ borderBottom: "1px solid", borderColor: "divider" }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <ScatterPlotIcon sx={{ color: "primary.main" }} />
                    <span>Scattered Plot</span>
                  </Box>
                </MenuItem>

                <MenuItem
                  value="bar_group"
                  data-barmode="group"
                  data-orientation="h"
                  sx={{ borderBottom: "1px solid", borderColor: "divider" }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <BarChartIcon
                      sx={{ color: "primary.main", transform: "rotate(90deg)" }}
                    />
                    <span>Grouped Bar</span>
                  </Box>
                </MenuItem>

                <MenuItem
                  value="bar_stacked"
                  data-barmode="stack"
                  data-orientation="h"
                  sx={{ borderBottom: "1px solid", borderColor: "divider" }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <StackedBarChartIcon
                      sx={{ color: "primary.main", transform: "rotate(90deg)" }}
                    />
                    <span>Stacked Bar</span>
                  </Box>
                </MenuItem>

                <MenuItem
                  value="histogram"
                  sx={{ borderBottom: "1px solid", borderColor: "divider" }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <HistogramIcon sx={{ color: "primary.main" }} />
                    <span>Histogram Bar</span>
                  </Box>
                </MenuItem>

                <MenuItem value="pie">
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <PieChartIcon sx={{ color: "primary.main" }} />
                    <span>Pie Chart</span>
                  </Box>
                </MenuItem>
              </Select>
            </Box>

            <FilterationForXAxis
              rowData={conversation.excelData}
              xaxisColumn={xaxisColumn}
              setXaxisColumn={setXaxisColumn}
            />

            <FilterationForYAxis
              rowData={conversation.excelData}
              yaxisColoumn={yaxisColoumn}
              setYaxisColoumn={setYaxisColoumn}
            />
          </Box>

          <Box style={{ borderLeft: "1px solid #dfdada", width: "100%" }}>
            {graphType === "histogram" && <HistogramComponent />}

            {graphType === "pie" && <PieComponent />}

            {graphType !== "histogram" && graphType !== "pie" && (
              <Plot
                data={getDynamicGraphData(
                  xaxisColumn,
                  yaxisColoumn,
                  conversation.excelData,
                  graphType,
                  orientation,
                  mode,
                  fill
                )}
                layout={{
                  title: `Dynamic ${
                    graphType.charAt(0).toUpperCase() + graphType.slice(1)
                  } Graph`,
                  barmode: barMode,
                  xaxis: {
                    title: {
                      text: xaxisColumn,
                      width: "10px",
                    },
                  },
                  yaxis: {
                    title: {
                      text: yaxisColoumn,
                    },
                  },
                  margin: {
                    l: 190, // Left margin to prevent cutting off text
                    r: 50, // Right margin
                    b: 100, // Bottom margin
                    t: 50, // Top margin
                  },
                }}
                config={{
                  responsive: true,
                }}
                style={{ width: "95%" }}
              />
            )}
          </Box>
        </Box>
      </div>
    </>
  );
};

const getDynamicGraphData = (
  xaxisColumn,
  yaxisColoumn,
  rowData,
  graphType,
  orientation,
  mode,
  fill
) => {
  const xData = rowData.map((item) => item[xaxisColumn]);
  const yData = rowData.map((item) => item[yaxisColoumn]);

  const colors = [
    "#FF5733",
    "#33FF57",
    "#3357FF",
    "#F333FF",
    "#FF3356",
    "#FF8C00",
    "#00BFFF",
  ];
  const colorArray = rowData.map((_, index) => colors[index % colors.length]);

  return [
    {
      x: xData,
      y: yData,
      type: graphType,
      orientation: orientation,
      mode: mode,
      fill: fill,
      marker: {
        size: 12,
        color: colorArray,
      },
    },
  ];
};

const HistogramComponent = () => {
  const [dataHistogram, setDataHistogram] = useState([
    12, 14, 16, 18, 12, 20, 18, 17, 14, 19, 20, 22, 24, 18, 17, 14,
  ]);

  return (
    <Plot
      data={[
        {
          type: "histogram",
          x: dataHistogram,
          nbinsx: 10,
          name: "Sample Data",
          marker: {
            color: "rgba(50, 171, 96, 0.6)",
          },
        },
      ]}
      layout={{
        width: "100%",
        height: "100%",
        bargroupgap: 0.2,
        title: {
          text: "Sampled Results",
        },
        xaxis: {
          title: {
            text: "Value",
          },
        },
        yaxis: {
          title: {
            text: "Count",
          },
        },
      }}
    />
  );
};

const PieComponent = () => {
  return (
    <Plot
      data={[
        {
          type: "pie",
          labels: ["A", "B", "C"],
          values: [10, 20, 30],
          hoverinfo: "label+percent",
          // textinfo: 'label+percent',
        },
      ]}
      layout={{
        width: "100%",
        height: "100%",
        title: {
          text: "Pie Results",
        },
        showlegend: true,
      }}
    />
  );
};

const FilterationForXAxis = ({ rowData, xaxisColumn, setXaxisColumn }) => {
  return (
    <>
      <Box
        sx={{
          mt: 3,
          p: 2,
          backgroundColor: "background.paper",
          borderRadius: 2,
          border: "1px solid",
          borderColor: "divider",
          boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
          transition: "all 0.2s ease",
          "&:hover": {
            borderColor: "primary.light",
            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
          },
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 2,
          }}
        >
          {/* X-Axis Label with alternative icon */}
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: 600,
              color: "text.primary",
              display: "flex",
              alignItems: "center",
              minWidth: 80,
            }}
          >
            <AxisIcon
              sx={{
                fontSize: 18,
                mr: 1,
                transform: "rotate(90deg)",
                color: "primary.main",
              }}
            />
            X-Axis
          </Typography>

          {/* Filter Component */}
          <Box
            sx={{
              flex: 1,
              ml: 1,
            }}
          >
            <FilterationForAxis
              rowData={rowData}
              axisColumn={xaxisColumn}
              setAxisColumn={setXaxisColumn}
              axisType="x"
              SetScaleType={SetScaleTypeForX}
            />
          </Box>
        </Box>
      </Box>
    </>
  );
};

const FilterationForYAxis = ({ rowData, yaxisColoumn, setYaxisColoumn }) => {
  return (
    <>
      <Box
        sx={{
          mt: 3,
          p: 2,
          backgroundColor: "background.paper",
          borderRadius: 2,
          border: "1px solid",
          borderColor: "divider",
          boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
          transition: "all 0.2s ease",
          "&:hover": {
            borderColor: "secondary.light",
            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
          },
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 2,
          }}
        >
          {/* Y-Axis Label with icon */}
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: 600,
              color: "text.primary",
              display: "flex",
              alignItems: "center",
              minWidth: 80,
            }}
          >
            <TrendingUp
              sx={{
                fontSize: 18,
                mr: 1,
                color: "secondary.main",
              }}
            />
            Y-Axis
          </Typography>

          {/* Filter Component */}
          <Box
            sx={{
              flex: 1,
              ml: 1,
            }}
          >
            <FilterationForAxis
              rowData={rowData}
              axisColumn={yaxisColoumn}
              setAxisColumn={setYaxisColoumn}
              axisType="y"
              SetScaleType={SetAggregateTypeForY}
            />
          </Box>
        </Box>
      </Box>
    </>
  );
};

const FilterationForAxis = ({
  rowData,
  axisColumn,
  setAxisColumn,
  axisType,
  SetScaleType,
}) => {
  const columnTypes = {};
  if (rowData.length === 0) return null;

  Object.keys(rowData[0]).forEach((key) => {
    const value = rowData[0][key];
    if (typeof value === "number") {
      columnTypes[key] = "numeric";
    } else if (typeof value === "boolean") {
      columnTypes[key] = "boolean";
    } else if (!isNaN(Date.parse(value))) {
      columnTypes[key] = "datetime";
    } else {
      columnTypes[key] = "string";
    }
  });

  const handleAxisColumn = (e) => {
    setAxisColumn(e.target.value);
  };

  return (
    <Box
      className="axisDropdown"
      sx={{
        width: "100%",
        fontFamily: '"Headland One", serif',
        position: "relative",
      }}
    >
      <FormControl fullWidth>
        <Select
          id={`${axisType}-axisType`}
          aria-label={`Select ${axisType} axis column`}
          displayEmpty
          onChange={handleAxisColumn}
          value={axisColumn || ""}
          renderValue={(selected) => {
            const lower = selected?.toLowerCase?.();
            if (lower === "order id" || lower === "customer id") {
              return axisType === "x"
                ? "Select X-axis column"
                : "Select Y-axis column";
            }
            return (
              selected ||
              (axisType === "x"
                ? "Select X-axis column"
                : "Select Y-axis column")
            );
          }}
          sx={{
            width: "100%",
            borderRadius: "6px",
            backgroundColor: "white !important",
            fontSize: "14px",
            color: axisColumn ? "#333" : "#999",
            height: "48px",
            "& .MuiSelect-select": {
              padding: "12px 16px",
              display: "flex",
              alignItems: "center",
              height: "100%",
              boxSizing: "border-box",
            },
            "& .MuiOutlinedInput-notchedOutline": {
              border: "1px solid #ddd",
            },
            "&:hover .MuiOutlinedInput-notchedOutline": {
              borderColor: "#999",
            },
            "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
              borderColor: "#1976d2",
              borderWidth: "1px",
              boxShadow: "0 0 0 2px rgba(25, 118, 210, 0.2)",
            },
          }}
          MenuProps={{
            PaperProps: {
              sx: {
                marginTop: "8px",
                borderRadius: "6px",
                boxShadow: "0 4px 20px rgba(0,0,0,0.12)",
                "& .MuiMenuItem-root": {
                  padding: "12px 16px",
                  fontSize: "14px",
                  minHeight: "auto",
                },
              },
            },
          }}
        >
          <MenuItem
            value=""
            disabled
            sx={{ color: "black", borderBottom: "1px solid #afafaf" }}
          >
            {axisType === "x" ? "Select X-axis column" : "Select Y-axis column"}
          </MenuItem>
          {Object.keys(columnTypes).map((colNames) => (
            <MenuItem
              key={colNames}
              value={colNames}
              sx={{
                color: "#333",
                "&:hover": {
                  backgroundColor: "rgba(25, 118, 210, 0.08)",
                },
              }}
            >
              {colNames}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
};

const SetScaleTypeForX = (type) => {
  switch (type) {
    case "numeric":
      return ["Number"];
    case "datetime":
      return ["Datetime"];
    case "string":
      return ["String"];
    case "boolean":
      return ["boolean"];
    default:
      return ["Default"];
  }
};

const SetAggregateTypeForY = (type) => {
  switch (type) {
    case "numeric":
      return ["Number", "String"];
    case "datetime":
      return ["Datetime", "String"];
    case "string":
      return ["String", "Datetime", "Number"];
    default:
      return ["Default"];
  }
};
