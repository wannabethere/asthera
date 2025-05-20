import React, { useState, useEffect } from "react";
import {
  Box,
  Button,
  ButtonGroup,
  ClickAwayListener,
  Divider,
  Grow,
  InputBase,
  ListItemIcon,
  Menu,
  MenuItem,
  MenuList,
  Paper,
  Popper,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from "@mui/material";

import { alpha, styled } from "@mui/material/styles";
import MuiAppBar from "@mui/material/AppBar";
import SearchIcon from "@mui/icons-material/Search";
import AddIcon from "@mui/icons-material/Add";
import { IoIosArrowDown } from "react-icons/io";
import { AiOutlineUpload } from "react-icons/ai";
import { LuFileSliders } from "react-icons/lu";
import { saveAs } from "file-saver";
import { useNavigate } from "react-router-dom";
import UpgradeIcon from "@mui/icons-material/Upgrade";
import HandshakeIcon from '@mui/icons-material/Handshake';

import { Document, Packer, Paragraph, TextRun } from "docx";
import ProfileComponent from "./ProfileComponent";

import { useConversation } from "../../context/ConversationContext";

import { MoreVert } from "@mui/icons-material";

const drawerWidth = 240;
const currentUser = JSON.parse(localStorage.getItem("currentUser"));

const Search = styled("div")(({ theme }) => ({
  position: "relative",
  borderRadius: theme.shape.borderRadius,
  border: "1px solid #dfdada",
  // backgroundColor: alpha(theme.palette.common.white, 0.15),
  background: " rgb(247, 246, 249)",
  "&:hover": {
    backgroundColor: alpha(theme.palette.common.white, 0.25),
  },
  marginRight: theme.spacing(2),
  marginLeft: 0,
  maxWidth: 400,
  width: "100% !important",
  [theme.breakpoints.up("sm")]: {
    marginLeft: theme.spacing(3),
    width: "auto",
  },
}));

const SearchIconWrapper = styled("div")(({ theme }) => ({
  padding: theme.spacing(0, 2),
  height: "100%",
  position: "absolute",
  pointerEvents: "none",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
}));

const StyledInputBase = styled(InputBase)(({ theme }) => ({
  color: "inherit",
  "& .MuiInputBase-input": {
    padding: theme.spacing(1, 1, 1, 0),
    // vertical padding + font size from searchIcon
    paddingLeft: `calc(1em + ${theme.spacing(4)})`,
    transition: theme.transitions.create("width"),
    width: "100%",
    [theme.breakpoints.up("md")]: {
      width: "20ch",
    },
  },
}));

const AppBar = styled(MuiAppBar, {
  shouldForwardProp: (prop) => prop !== "open",
})(({ theme }) => ({
  zIndex: theme.zIndex.drawer + 1,
  transition: theme.transitions.create(["width", "margin"], {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  variants: [
    {
      props: ({ open }) => open,
      style: {
        marginLeft: drawerWidth,
        width: `calc(100% - ${drawerWidth}px)`,
        transition: theme.transitions.create(["width", "margin"], {
          easing: theme.transitions.easing.sharp,
          duration: theme.transitions.duration.enteringScreen,
        }),
      },
    },
  ],
}));

export const AppTopToolBar = ({ sessionId }) => {
  const { conversations } = useConversation();

  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);

  const handleMenuClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const [collabOpen, setCollabOpen] = useState(false);
  const [collabEmail, setCollabEmail] = useState("");
  const [collabRole, setCollabRole] = useState("read");
  const [inviteMessage, setInviteMessage] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [collaborators, setCollaborators] = useState([]);

  const fetchCollaborators = async () => {
    if (!sessionId) return;
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/thread/${sessionId}/collaborators`
      );
      const data = await res.json();
      setOwnerEmail(data.owner);
      setCollaborators([]);
    } catch (err) {
      console.error("Error fetching collaborators:", err);
    }
  };

  // Fetch collaborators when dialog opens
  useEffect(() => {
    if (collabOpen) fetchCollaborators();
  }, [collabOpen]);

  const handleInviteCollaborator = async () => {
    const currentUser = JSON.parse(localStorage.getItem("currentUser"));
    // const sessionId = sessionId; // assuming session ID is available

    if (!sessionId || !currentUser) {
      setInviteMessage("Session or user missing.");
      return;
    }

    try {
      const res = await fetch("http://127.0.0.1:8000/thread/add-collaborator", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          collaborator_email: collabEmail,
          role: collabRole,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setInviteMessage(" Collaborator invited!");
      } else {
        setInviteMessage(` ${data.detail}`);
      }
    } catch (err) {
      setInviteMessage("Error sending invite.");
    }
  };

  // const downloadConversationAsWord = () => {
  //   const doc = new Document({
  //     sections: [
  //       {
  //         properties: {},
  //         children: conversations.flatMap((item, index) => {
  //           const questionPara = new Paragraph({
  //             spacing: { after: 100 },
  //             children: [
  //               new TextRun({
  //                 text: `${item.sender}: ${item.question}`,
  //                 bold: true,
  //                 color: "#0000FF",
  //               }),
  //             ],
  //           });

  //           const responsePara = new Paragraph({
  //             spacing: { after: 200 },
  //             children: [
  //               new TextRun({ text: `Bot: ${stripHTML(item.response)}` }),
  //             ],
  //           });

  //           return [questionPara, responsePara];
  //         }),
  //       },
  //     ],
  //   });

  //   Packer.toBlob(doc).then((blob) => {
  //     saveAs(blob, "conversation-thread.docx");
  //   });
  // };

  const downloadAsJupyterNotebook = () => {
    const cells = conversations.flatMap(
      ({ question, sender, response }, index) => [
        {
          cell_type: "markdown",
          metadata: {},
          source: [`**${sender}:** ${question}`],
        },
        {
          cell_type: "markdown",
          metadata: {},
          source: [`**Bot:** ${stripHTML(response)}`],
        },
      ]
    );

    const notebook = {
      cells,
      metadata: {
        kernelspec: {
          display_name: "Python 3",
          language: "python",
          name: "python3",
        },
        language_info: {
          name: "python",
          version: "3.x",
        },
      },
      nbformat: 4,
      nbformat_minor: 5,
    };

    const blob = new Blob([JSON.stringify(notebook, null, 2)], {
      type: "application/json",
    });

    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "conversation.ipynb";
    link.click();
  };

  const stripHTML = (html) => {
    const div = document.createElement("div");
    div.innerHTML = html;
    return div.textContent || div.innerText || "";
  };

  // const handleDownloadWordClick = () => {
  //   downloadConversationAsWord(); // Call your Word export function
  //   handleClose();
  // };

  const handleDownloadNotebookClick = () => {
    downloadAsJupyterNotebook(); // Call your Jupyter export function
    handleClose();
  };

  const handleRoleUpdate = async (email, newRole) => {
    try {
      const res = await fetch("http://127.0.0.1:8000/thread/add-collaborator", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          collaborator_email: email,
          role: newRole,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setCollaborators(data.collaborators || []);
        setInviteMessage(`Updated ${email}'s role.`);
      } else {
        setInviteMessage(`Failed to update role: ${data.detail}`);
      }
    } catch (err) {
      console.error("Failed to update collaborator role:", err);
      setInviteMessage("Error updating role.");
    }
  };

  const navigate = useNavigate();

  return (
    <>
      <AppBar
        position="fixed"
        className="appBar"
        sx={{
          color: "gray",
          background: "transparent",
          backdropFilter: "blur(9px)",
          WebkitBackdropFilter: "blur(9px)",
          borderBottom: "1px solid rgba(255, 255, 255, 0.3)",
          boxShadow: "0px 2px 3px -1px rgba(0,0,0,0.2)",
          transition:
            "backdrop-filter 0.25s linear, -webkit-backdrop-filter 0.25s linear",
        }}
      >
        <Toolbar className="Navbar_container">
          <Typography variant="h6" noWrap component="div">
            GenAI
          </Typography>

          <Box sx={{ flexGrow: 1, display: "flex", justifyContent: "center" }}>
            <Search
              sx={{
                backgroundColor: (theme) =>
                  theme.palette.mode === "dark" ? "#424242" : "#f1f1f1",
                "&:hover": {
                  backgroundColor: (theme) =>
                    theme.palette.mode === "dark" ? "#535353" : "#e0e0e0",
                },
              }}
            >
              <SearchIconWrapper>
                <SearchIcon />
              </SearchIconWrapper>
              <StyledInputBase
                sx={{ color: "grey" }}
                placeholder="Search Workspace"
                inputProps={{ "aria-label": "search" }}
              />
            </Search>
          </Box>
          <Tooltip
            title="View or add Members into Collaboration"
            placement="left"
          >
            <Button
              onClick={() => setCollabOpen(true)}
              variant="outlined"
              startIcon={<HandshakeIcon sx={{ fontSize: "1rem" }} />}
              sx={{
                m: 1,
                px: 2,
                py: "6px",
                gap: 1,
                color: (theme) =>
                  theme.palette.mode === "dark"
                    ? theme.palette.grey[100]
                    : theme.palette.grey[900],
                backgroundColor: (theme) =>
                  theme.palette.mode === "dark"
                    ? theme.palette.grey[800] + "99" // Slightly transparent in dark mode
                    : theme.palette.common.white,
                borderRadius: "20px",
                border: (theme) =>
                  `1px solid ${
                    theme.palette.mode === "dark"
                      ? theme.palette.grey[700]
                      : theme.palette.grey[300]
                  }`,
                textTransform: "none",
                fontWeight: 500,
                fontSize: "0.875rem",
                letterSpacing: "0.025em",
                transition: "all 0.2s ease-in-out",
                "&:hover": {
                  backgroundColor: (theme) =>
                    theme.palette.mode === "dark"
                      ? theme.palette.grey[700]
                      : theme.palette.grey[100],
                  borderColor: (theme) =>
                    theme.palette.mode === "dark"
                      ? theme.palette.grey[600]
                      : theme.palette.grey[400],
                  transform: "translateY(-1px)",
                  boxShadow: (theme) =>
                    theme.palette.mode === "dark"
                      ? "0 2px 8px rgba(0, 0, 0, 0.3)"
                      : "0 2px 8px rgba(0, 0, 0, 0.1)",
                },
                "& .MuiButton-startIcon": {
                  color: (theme) =>
                    theme.palette.mode === "dark"
                      ? theme.palette.secondary.light
                      : theme.palette.secondary.main,
                },
                "&:active": {
                  transform: "translateY(0)",
                },
              }}
            >
              Collaboration
            </Button>
          </Tooltip>

          <Tooltip placement="left">
            <Button
              onClick={handleMenuClick}
              variant="outlined"
              sx={{
                m: 1,
                color: (theme) =>
                  theme.palette.mode === "dark" ? "white" : "black",
                backgroundColor: (theme) =>
                  theme.palette.mode === "dark" ? "#424242" : "white",
                borderRadius: "20px",
                border: (theme) =>
                  theme.palette.mode === "dark"
                    ? "1px solid rgba(255, 255, 255, 0.2)"
                    : "1px solid rgba(0, 0, 0, 0.1)",
                overflow: "visible",
                textTransform: "none",
                "&:hover": {
                  backgroundColor: (theme) =>
                    theme.palette.mode === "dark"
                      ? theme.palette.grey[700]
                      : theme.palette.grey[100],
                  borderColor: (theme) =>
                    theme.palette.mode === "dark"
                      ? theme.palette.grey[600]
                      : theme.palette.grey[400],
                  transform: "translateY(-1px)",
                  boxShadow: (theme) =>
                    theme.palette.mode === "dark"
                      ? "0 2px 8px rgba(0, 0, 0, 0.3)"
                      : "0 2px 8px rgba(0, 0, 0, 0.1)",
                },
              }}
            >
              <UpgradeIcon fontSize="small" />
              Export
            </Button>
          </Tooltip>

          <Menu anchorEl={anchorEl} open={open} onClose={handleClose}>
            {/* <MenuItem onClick={handleDownloadWordClick}>
              Download as Word
            </MenuItem> */}
            <MenuItem onClick={handleDownloadNotebookClick}>
              Download as Jupyter Notebook
            </MenuItem>
          </Menu>

          <Stack direction="row" spacing={3}>
            <ProfileComponent />
          </Stack>
        </Toolbar>
      </AppBar>

      <Dialog
        open={collabOpen}
        onClose={() => setCollabOpen(false)}
        PaperProps={{
          sx: {
            width: "700px",
            maxWidth: "90%", // responsive fallback
            padding: 2,
          },
        }}
      >
        <DialogTitle>Invite Collaborator</DialogTitle>
        <DialogContent>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            Owner
          </Typography>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              mb: 2,
              pl: 1,
            }}
          >
            <Box
              sx={{
                bgcolor: "#4caf50",
                color: "#fff",
                width: 32,
                height: 32,
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                mr: 1,
                fontWeight: "bold",
              }}
            >
              {ownerEmail ? ownerEmail.charAt(0).toUpperCase() : 'U'}
            </Box>
            <Typography>{ownerEmail || 'Unknown User'} (you)</Typography>
            <Box sx={{ ml: "auto", fontSize: "12px", color: "gray" }}>
              Owner
            </Box>
          </Box>

          <Divider sx={{ my: 1 }} />

          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            Collaborators
          </Typography>
          {collaborators?.length === 0 ? (
            <Typography>No collaborators added yet.</Typography>
          ) : (
            collaborators.map((collab, index) => (
              <Box
                key={index}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  mb: 1,
                  pl: 1,
                  gap: 1,
                }}
              >
                <Box
                  sx={{
                    bgcolor: "#2196f3",
                    color: "#fff",
                    width: 32,
                    height: 32,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: "bold",
                  }}
                >
                  {collab.email ? collab.email.charAt(0).toUpperCase() : 'U'}
                </Box>
                <Typography sx={{ flex: 1 }}>{collab.email}</Typography>

                {currentUser.email === ownerEmail ? (
                  <TextField
                    select
                    size="small"
                    value={collab.role}
                    onChange={(e) =>
                      handleRoleUpdate(collab.email, e.target.value)
                    }
                    sx={{ width: 120 }}
                  >
                    <MenuItem value="read">Read</MenuItem>
                    <MenuItem value="read-write">Read & Write</MenuItem>
                  </TextField>
                ) : (
                  <Typography sx={{ fontSize: "14px", color: "gray" }}>
                    {collab.role}
                  </Typography>
                )}
              </Box>
            ))
          )}

          <Divider sx={{ my: 2 }} />

          {/* Invitation fields only visible to owner */}
          {currentUser.email === ownerEmail && (
            <>
              <Typography variant="subtitle1" sx={{ mb: 1 }}>
                Add new collaborator
              </Typography>
              <TextField
                label="Collaborator Email"
                value={collabEmail}
                onChange={(e) => setCollabEmail(e.target.value)}
                fullWidth
                margin="dense"
              />
              <TextField
                select
                label="Role"
                value={collabRole}
                onChange={(e) => setCollabRole(e.target.value)}
                fullWidth
                margin="dense"
              >
                <MenuItem value="read">Read</MenuItem>
                <MenuItem value="read-write">Read & Write</MenuItem>
              </TextField>
              {inviteMessage && <p>{inviteMessage}</p>}
            </>
          )}
        </DialogContent>
        <DialogActions>
          {currentUser.email === ownerEmail && (
            <Button onClick={handleInviteCollaborator}>Invite</Button>
          )}
          <Button onClick={() => setCollabOpen(false)}>Cancel</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};
