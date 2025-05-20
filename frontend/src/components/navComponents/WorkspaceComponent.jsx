import React, { useState, useEffect } from "react";
import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Typography,
  Snackbar,
  Alert,
  FormControl,
  Select,
  MenuItem,
  Tooltip,
} from "@mui/material";
import { Add, Delete } from "@mui/icons-material";
import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, ModuleRegistry, themeQuartz } from "ag-grid-community";
import { useNavigate } from "react-router-dom";
import "ag-grid-community/styles/ag-theme-quartz.css";
import StartIcon from '@mui/icons-material/Start';
import { alpha } from '@mui/system';

const myTheme = themeQuartz.withParams({
  headerFontFamily: '"IBM Plex Sans", system-ui, sans-serif !important',
  cellFontFamily: '"IBM Plex Sans", system-ui, sans-serif !important',
  wrapperBorder: true,
  headerRowBorder: true,
  // headerColumnBorder:true,
  rowBorder: { style: "solid", width: 1, color: "#ededed" },
  columnBorder: { style: "solid", color: "#ededed" },
});

export default function WorkspaceComponent({
  threads,
  setThreads,
  currentThreadIndex,
  setCurrentThreadIndex,
}) {
  const navigate = useNavigate();
  const currentUser = JSON.parse(localStorage.getItem("currentUser"));

  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [collaborators, setCollaborators] = useState([]);
  const [workspaceSessions, setWorkspaceSessions] = useState([]);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: "",
    severity: "success",
  });

  useEffect(() => {
    fetchWorkspaces();
    ModuleRegistry.registerModules([AllCommunityModule]);
  }, []);

  const fetchWorkspaces = async () => {
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/chat/sessions?user_email=${currentUser.email}`
      );
      const data = await res.json();
      if (data.sessions) {
        const workspacesWithCollabs = data.sessions.filter(
          (session) => session.collaborators && session.collaborators.length > 0
        );
        setWorkspaceSessions(workspacesWithCollabs);
      }
    } catch (error) {
      console.error("Error fetching sessions:", error);
    }
  };

  const handleOpenDialog = () => {
    setOpen(true);
    setCollaborators([
      {
        id: `${Date.now()}`,
        email: currentUser.email,
        role: "owner",
        isOwner: true,
      },
    ]);
  };

  const handleAddCollaborator = () => {
    setCollaborators((prev) => [
      ...prev,
      { id: `${Date.now()}`, email: "", role: "read", isOwner: false },
    ]);
  };

  const handleRemoveCollaborator = (index) => {
    if (index === 0) return;
    setCollaborators((prev) => prev.filter((_, i) => i !== index));
  };

  const handleCreate = async () => {
    try {
      const nonOwnerCollaborators = collaborators
        .slice(1)
        .filter((collab) => collab.email.trim() !== "");

      if (nonOwnerCollaborators.length === 0) {
        throw new Error(
          "Please add at least one collaborator before creating the workspace."
        );
      }

      const formData = new FormData();
      formData.append("owner_email", currentUser.email);
      formData.append("workspace_name", name);
      formData.append("user_input", `Workspace created: ${name}`);

      const res = await fetch("http://127.0.0.1:8000/chat/start", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error("Failed to create workspace");
      }

      const data = await res.json();
      const sessionId = data.session_id;

      for (const collab of nonOwnerCollaborators) {
        const collabRes = await fetch(
          "http://127.0.0.1:8000/thread/add-collaborator",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sessionId,
              collaborator_email: collab.email,
              role: collab.role,
            }),
          }
        );

        if (!collabRes.ok) {
          const errorData = await collabRes.json();
          await fetch(`http://127.0.0.1:8000/chat/${sessionId}`, {
            method: "DELETE",
          });

          throw new Error(errorData.detail || "Failed to add collaborator");
        }
      }

      // ✅ Create First Message manually
      const firstMessage = {
        QuestionId: data.question_id,
        question: `Workspace created: ${name}`,
        response: data.response,
        history: [],
        isEdited: false,
        sender: currentUser.email,
      };

      // ✅ Create a new Thread Object with first message
      const newThread = {
        session_id: sessionId,
        workspace_name: name,
        name: `Thread ${threads.length + 1}`,
        question: `Workspace created: ${name}`,
        owner: currentUser.email,
        pinned: false,
        messages: [firstMessage], // ✨ messages populated from API!
        collaborators: collaborators.map((c) => ({
          email: c.email,
          role: c.role,
        })),
      };

      setThreads((prevThreads) => [...prevThreads, newThread]);
      setCurrentThreadIndex(threads.length);

      setSnackbar({
        open: true,
        message: "Workspace and thread created!",
        severity: "success",
      });

      fetchWorkspaces();
      setOpen(false);
      setName("");
      setCollaborators([]);
    } catch (error) {
      console.error("Error during workspace creation:", error);
      setSnackbar({
        open: true,
        message: error.message || "Error creating workspace",
        severity: "error",
      });
    }
  };

  const handleContinueChat = (sessionId) => {
    navigate(`/navbar/thread?id=${sessionId}`);
  };

  const handleDeleteWorkspace = async (sessionId) => {
    try {
      await fetch(`http://127.0.0.1:8000/chat/${sessionId}`, {
        method: "DELETE",
      });

      fetchWorkspaces(); // Refresh workspace list

      const index = threads.findIndex(
        (thread) => thread.session_id === sessionId
      );

      if (index !== -1) {
        const updatedThreads = threads.filter((_, i) => i !== index);
        setThreads(updatedThreads);

        if (updatedThreads.length === 0) {
          setCurrentThreadIndex(-1);
        } else if (index <= currentThreadIndex) {
          setCurrentThreadIndex(Math.max(0, currentThreadIndex - 1));
        }
      }

      setSnackbar({
        open: true,
        message: "Workspace deleted successfully!",
        severity: "success",
      });
    } catch (error) {
      console.error("Error deleting workspace:", error);
      setSnackbar({
        open: true,
        message: "Failed to delete workspace",
        severity: "error",
      });
    }
  };

  // Workspaces Grid Columns
  const workspaceColDefs = [
    {
      headerName: "Workspace Name",
      field: "workspace_name",
      flex: 1,
      minWidth: 180,
      cellStyle: {
        fontWeight: '500',
        display: 'flex',
        alignItems: 'center'
      }
    },
    {
      headerName: "Owner",
      field: "owner",
      flex: 1,
      minWidth: 150,
      cellStyle: { color: '#555' }
    },
    {
      headerName: "Collaborators",
      field: "collaborators",
      flex: 1,
      minWidth: 200,
      valueGetter: (params) => params.data.collaborators.map((c) => c.email).join(", "),
      cellStyle: {
        color: '#666',
        fontSize: '0.875rem'
      },
      tooltipField: "collaborators",
      tooltipValueGetter: (params) => params.value // Shows full list on hover
    },
    {
      headerName: "Actions",
      field: "actions",
      cellRenderer: (params) => (
        <Box sx={{
          display: "flex",
          gap: 1,
          justifyContent: 'center',
          alignItems: 'center',
          height: '100%',
        }}>
          <Tooltip title="Continue chat in this workspace" arrow>
            <Button
              size="small"
              variant="contained"
              // color="primary"
              onClick={(e) => {
                e.stopPropagation();
                handleContinueChat(params.data.session_id);
              }}
              sx={{
                color: (theme) =>
                  theme.palette.mode === "dark" ? "white" : "white",
                backgroundColor: (theme) =>
                  theme.palette.mode === "dark" ? "#424242" : "#979797",
                border: (theme) =>
                  theme.palette.mode === "dark"
                    ? "1px solid rgba(255, 255, 255, 0.2)"
                    : "1px solid rgba(0, 0, 0, 0.1)",
                minWidth: '80px',
                textTransform: 'none',
                boxShadow: 'none',
                '&:hover': {
                  boxShadow: '0 2px 5px rgba(0,0,0,0.2)'
                }
              }}
            >
              Chat
            </Button>
          </Tooltip>
          <Tooltip title="Delete this workspace" arrow>
            <Button
              size="small"
              variant="outlined"
              color="error"
              onClick={(e) => {
                e.stopPropagation();
                handleDeleteWorkspace(params.data.session_id);
              }}
              sx={{
                minWidth: '80px',
                textTransform: 'none',
                '&:hover': {
                  backgroundColor: 'error.light',
                  color: 'white'
                }
              }}
            >
              Delete
            </Button>
          </Tooltip>
        </Box>
      ),
      flex: 1,
      minWidth: 200,
      sortable: false,
      filter: false,
      cellStyle: {
        justifyContent: 'center',
        padding: '8px 0'
      }
    },
  ];

  // Collaborators Grid Columns
  const columnDefs = [
    {
      headerName: "Email",
      field: "email",
      editable: false,
      flex: 1,
      cellStyle: {
        padding: '0px',
        display: 'flex',
        alignItems: 'center'
      },
      cellRenderer: React.memo((params) => {
        const inputRef = React.useRef(null);
        const [localValue, setLocalValue] = React.useState(params.value || '');

        // Only update parent state when input loses focus
        const handleBlur = () => {
          if (localValue !== params.value) {
            const updated = [...collaborators];
            updated[params.node.rowIndex] = {
              ...updated[params.node.rowIndex],
              email: localValue
            };
            setCollaborators(updated);
          }
        };

        // Sync with external changes
        React.useEffect(() => {
          setLocalValue(params.value || '');
        }, [params.value]);

        return (
          <TextField
            inputRef={inputRef}
            value={localValue}
            onChange={(e) => setLocalValue(e.target.value)}
            onBlur={handleBlur}
            variant="outlined"
            size="small"
            fullWidth
            disabled={params.data.isOwner}
            // placeholder={localValue === '' ? "Enter the register email" : undefined}
            sx={{
              '& .MuiOutlinedInput-root': {
                height: '36px',
                fontSize: '13px',
                '&.Mui-disabled': {
                  '& fieldset': { border: 'none' },
                  px: 2,
                  backgroundColor: 'transparent'
                }
              },
              '& .Mui-disabled': {
                padding: 0,
                WebkitTextFillColor: 'unset'
              }
            }}
            InputProps={{
              notched: !params.data.isOwner,
              onKeyDown: (e) => {
                if (e.key === 'Enter') {
                  inputRef.current.blur();
                }
              }
            }}
          />
        );
      }, (prevProps, nextProps) => {
        // Only re-render if the value actually changed
        return prevProps.value === nextProps.value &&
          prevProps.data.isOwner === nextProps.data.isOwner;
      })
    },
    {
      headerName: "Role",
      field: "role",
      editable: false,
      cellStyle: (params) => ({
        padding: '0%',
        display: 'flex',
        alignItems: 'center',
        // Remove background color for owner rows
        backgroundColor: 'transparent'
      }),
      cellRenderer: (params) => {
        if (params.data.isOwner) {
          return (
            <Box sx={{
              padding: '8px 12px',
              width: '100%',
              fontSize: '13px'
            }}>
              Owner
            </Box>
          );
        }

        return (
          <FormControl fullWidth size="small" variant="outlined">
            <Select
              value={params.value || 'read'}
              onChange={(e) => {
                const updated = [...collaborators];
                updated[params.node.rowIndex] = {
                  ...updated[params.node.rowIndex],
                  role: e.target.value
                };
                setCollaborators(updated);
              }}
              sx={{
                height: '36px',
                fontSize: "13px",
                '& .MuiOutlinedInput-notchedOutline': {
                  border: params.data.isOwner ? 'none' : undefined
                },
                '& .MuiSelect-select': {
                  padding: '8px 32px 8px 12px',
                  backgroundColor: 'transparent'
                },
                '&.Mui-disabled': {
                  '& .MuiOutlinedInput-notchedOutline': {
                    border: 'none'
                  },
                  '& .MuiSelect-select': {
                    backgroundColor: 'transparent',
                    padding: '8px 12px', // Adjust padding when no dropdown icon
                    '-webkit-text-fill-color': 'inherit' // Fix text color in Safari
                  }
                }
              }}
              disabled={params.data.isOwner}
            >
              <MenuItem sx={{ fontSize: "13px" }} value="read">READ</MenuItem>
              <MenuItem sx={{ fontSize: "13px" }} value="read-write">READ & WRITE</MenuItem>
            </Select>
          </FormControl>
        );
      },
      flex: 1,
      suppressNavigable: true
    },
    {
      headerName: "Actions",
      field: "actions",
      cellRenderer: (params) =>
        !params.data.isOwner && (
          <IconButton
            onClick={(e) => {
              e.stopPropagation();
              handleRemoveCollaborator(params.node.rowIndex);
            }}
            sx={{
              color: (theme) => theme.palette.error.main,
              '&:hover': {
                backgroundColor: (theme) => theme.palette.error.light,
                color: (theme) => theme.palette.error.contrastText
              }
            }}
          >
            <Delete fontSize="small" />
          </IconButton>
        ),
      flex: 0.5,
      cellStyle: {
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center'
      },
      suppressNavigable: true,
      sortable: false,
      filter: false
    },
  ];

  return (
    <Box sx={{ p: 4, mt: 6, }}>
      {/* ➕ New Workspace Button */}
      <Box textAlign="center" mb={6}>
        <Button
          variant="contained"
          size="large"
          onClick={handleOpenDialog}
          sx={{
            borderRadius: '10px',
            px: 4,
            py: 1.2,
            fontSize: '1rem',
            fontWeight: 600,
            letterSpacing: '0.3px',
            backgroundColor: (theme) =>
              theme.palette.mode === "dark" ? "#424242" : "#828282",
            color: (theme) =>
              theme.palette.mode === "dark" ? "white" : "white",
            border: '1px solid rgba(255, 255, 255, 0.2)',
            boxShadow: '0 4px 8px rgba(0, 0, 0, 0.2)',
            textTransform: 'none',
            position: 'relative',
            overflow: 'hidden',
            '&:hover': {
              // backgroundColor: '#111',
              backgroundColor: (theme) =>
                theme.palette.mode === "dark" ? "#636363" : "#4e4e4e",
              boxShadow: '0 6px 12px rgba(0, 0, 0, 0.25)',
              transform: 'translateY(-1px)',
              '&::before': {
                opacity: 0.1
              }
            },
            '&:active': {
              transform: 'translateY(0)'
            },
            '&::before': {
              content: '""',
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              background: 'linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.3) 50%, rgba(255,255,255,0) 100%)',
              opacity: 0,
              transition: 'opacity 0.3s ease'
            },
            transition: 'all 0.3s ease'
          }}
          startIcon={
            <StartIcon sx={{
              fontSize: '1.3rem',
              color: 'white',
              transition: 'transform 0.2s ease',
              '.MuiButton-contained:hover &': {
                transform: 'translateX(2px)'
              }
            }} />
          }
        >
          New Workspace
        </Button>
      </Box>

      {/* Workspaces Grid */}
      <Box sx={{
        marginTop: 3,
        // height: "500px",
        // width: "100%",
        borderRadius: 2,
        overflow: "hidden",
        // boxShadow: (theme) => theme.shadows[1],
        boxShadow: "rgba(100, 100, 111, 0.2) 0px 7px 29px 0px",
        // border: (theme) => `1px solid ${theme.palette.divider}`,
        backgroundColor: (theme) => theme.palette.background.paper
      }}>
        <div
          className="ag-theme-quartz"
          style={{
            // height: "100%", width: "100%",
            backgroundColor: (theme) =>
              theme.palette.mode === "dark" ? "#424242" : "white",
          }}
        >
          <AgGridReact
            rowData={workspaceSessions}
            columnDefs={workspaceColDefs}
            theme={myTheme}
            defaultColDef={{
              sortable: false,
              filter: true,
              editable: false,
              flex: 1,
              minWidth: 80,
              maxWidth: 300,
            }}
            // Pagination properties
            pagination={true}
            paginationPageSize={10}
            domLayout="autoHeight"
            headerHeight={48}
            rowHeight={48}
            suppressScrollOnNewData={true}
            suppressCellFocus={true}
            suppressClickEdit={true}
            singleClickEdit={false}
            stopEditingWhenCellsLoseFocus={true}
          />
        </div>
      </Box>

      {/* Create Workspace Dialog */}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        fullWidth
        maxWidth="sm"
        PaperProps={{
          sx: {
            borderRadius: 3,
            background: (theme) => theme.palette.background.paper,
            boxShadow: (theme) => theme.shadows[5],
            overflow: "hidden"
          },
        }}
      >
        <DialogTitle sx={{
          fontWeight: 700,
          fontSize: "1.25rem",
          py: 2,
          px: 3,
          borderBottom: (theme) => `1px solid ${theme.palette.divider}`
        }}>
          Create New Workspace
        </DialogTitle>

        <DialogContent dividers sx={{ py: 2, px: 3 }}>
          <TextField
            label="Workspace Name"
            fullWidth
            value={name}
            onChange={(e) => setName(e.target.value)}
            margin="normal"
            variant="outlined"
            sx={{ mb: 3 }}
            InputProps={{
              sx: { borderRadius: 1 }
            }}
          />

          <Box sx={{ mt: 3 }} >
            <Typography variant="subtitle1" fontWeight={600} mb={2}>
              Collaborators
            </Typography>

            <Box
              sx={{
                height: 300,
                border: (theme) => `1px solid ${theme.palette.divider}`,
                borderRadius: 1,
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
                backgroundColor: (theme) => theme.palette.background.default
              }}
            >
              <div
                className="ag-theme-alpine"
                style={{
                  height: 250,
                  width: "100%",
                  '--ag-borders': 'none',
                  '--ag-border-radius': '0px'
                }}
              >
                <AgGridReact
                  rowData={collaborators}
                  columnDefs={columnDefs}
                  getRowId={(params) => params.data.id}
                  stopEditingWhenCellsLoseFocus
                  domLayout="autoHeight"
                  headerHeight={40}
                  rowHeight={40}
                  onCellValueChanged={(params) => {
                    const updated = [...collaborators];
                    updated[params.node.rowIndex] = {
                      ...updated[params.node.rowIndex],
                      [params.colDef.field]: params.newValue,
                    };
                    setCollaborators(updated);
                  }}
                />
              </div>

              <Box
                sx={{
                  p: 2,
                  borderTop: (theme) => `1px solid ${theme.palette.divider}`,
                  backgroundColor: (theme) => theme.palette.mode === 'dark'
                    ? alpha(theme.palette.primary.dark, 0.1)
                    : alpha(theme.palette.primary.light, 0.05),
                  textAlign: "center",
                  transition: 'background-color 0.3s ease',
                  '&:hover': {
                    backgroundColor: (theme) => theme.palette.mode === 'dark'
                      ? alpha(theme.palette.primary.dark, 0.2)
                      : alpha(theme.palette.primary.light, 0.1)
                  }
                }}
              >
                <Button
                  startIcon={<Add sx={{
                    transition: 'transform 0.2s ease',
                    '.MuiButton-root:hover &': {
                      transform: 'scale(1.2)'
                    }
                  }} />}
                  size="medium"
                  onClick={handleAddCollaborator}
                  variant="outlined"
                  sx={{
                    color: (theme) => theme.palette.primary.main,
                    borderColor: (theme) => alpha(theme.palette.primary.main, 0.3),
                    backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.04),
                    fontWeight: 600,
                    letterSpacing: '0.5px',
                    px: 3,
                    py: 1,
                    borderRadius: '8px',
                    textTransform: 'none',
                    transition: 'all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
                    '&:hover': {
                      backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.1),
                      borderColor: (theme) => theme.palette.primary.main,
                      boxShadow: '0 4px 8px rgba(0,0,0,0.1)',
                      transform: 'translateY(-1px)'
                    },
                    '&:active': {
                      transform: 'translateY(0)'
                    }
                  }}
                >
                  Add New Collaborator
                </Button>
              </Box>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions sx={{
          py: 2,
          px: 3,
          borderTop: (theme) => `1px solid ${theme.palette.divider}`,
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          gap: 2,
          backgroundColor: (theme) => theme.palette.background.default
        }}>
          <Button
            onClick={() => setOpen(false)}
            sx={{

              fontWeight: 500,
              textTransform: 'none',
              minWidth: 100,
              px: 2,
              py: 1,
              borderRadius: '6px',
              backgroundColor: (theme) => theme.palette.mode === 'dark' ? theme.palette.error.dark : '#d0000099',
              color: (theme) => theme.palette.common.white,
              '&:hover': {
                backgroundColor: (theme) => theme.palette.mode === 'dark' ? theme.palette.error.main : '#c62828d9',
                boxShadow: (theme) => theme.shadows[2]
              },
              border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? theme.palette.grey[800] : theme.palette.grey[300]}`,
              '&:hover': {
                backgroundColor: (theme) => theme.palette.mode === 'dark' ? theme.palette.error.main : theme.palette.error.dark,

              },
            }}
          >
            Cancel
          </Button>

          <Button
            onClick={handleCreate}
            variant="contained"
            disableElevation
            sx={{
              px: 3,
              py: 1,
              fontWeight: 600,
              textTransform: 'none',
              borderRadius: '6px',
              minWidth: 180,
              background: "transparent",
              color: (theme) => theme.palette.mode === 'dark' ? theme.palette.grey[300] : theme.palette.grey[800],
              border: (theme) => `1px solid ${theme.palette.mode === 'dark' ? theme.palette.grey[800] : theme.palette.grey[300]}`,
              '&:hover': {
                backgroundColor: (theme) => theme.palette.mode === 'dark' ? theme.palette.grey[800] : theme.palette.grey[100],
                borderColor: (theme) => theme.palette.mode === 'dark' ? theme.palette.grey[600] : theme.palette.grey[400],
                boxShadow: (theme) => theme.shadows[2]
              },
              '&.Mui-disabled': {
                backgroundColor: (theme) => theme.palette.action.disabledBackground,
                color: (theme) => theme.palette.action.disabled
              }
            }}
          >
            Create Workspace
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: "top", horizontal: "center" }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: "100%" }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
