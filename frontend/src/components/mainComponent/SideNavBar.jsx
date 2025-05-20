import * as React from "react";
import {
  Box,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Tooltip,
  Typography,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Menu,
  MenuItem,
  Collapse,
  Divider,
} from "@mui/material";
import { styled } from "@mui/material/styles";
import MuiDrawer from "@mui/material/Drawer";
import CssBaseline from "@mui/material/CssBaseline";
import { LuChevronsRight } from "react-icons/lu";
import { HiMiniChevronDoubleLeft } from "react-icons/hi2";
import { GrProjects } from "react-icons/gr";
import { FaDatabase } from "react-icons/fa";
import { LuFileSliders } from "react-icons/lu";
import { CiSettings } from "react-icons/ci";
import { IoHelpCircleOutline } from "react-icons/io5";
import { FaPlus } from "react-icons/fa6";
import { HiChevronDoubleDown } from "react-icons/hi2";
import { TiMessages } from "react-icons/ti";
import { SiPinboard } from "react-icons/si";
import { BsThreeDotsVertical } from "react-icons/bs";
import CreateOutlinedIcon from "@mui/icons-material/CreateOutlined";
import PushPinOutlinedIcon from "@mui/icons-material/PushPinOutlined";
import DeleteForeverOutlinedIcon from "@mui/icons-material/DeleteForeverOutlined";
import PushPinIcon from "@mui/icons-material/PushPin";
import "../../css/NavBar.css";

import { AppTopToolBar } from "./TopBar";
import { ProjectComponent } from "../navComponents/ProjectsComponent";
import { CollectionComponent } from "../navComponents/CollectionComponent";
import WorkspaceComponent from "../navComponents/WorkspaceComponent";
import { useEffect } from "react";
import { useThreads } from "../../context/ThreadsContext";
import { useNavigate, useLocation } from "react-router-dom";

const drawerWidth = 255;

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
  width: `calc(${theme.spacing(7)} + 1px)`,
  [theme.breakpoints.up("sm")]: {
    width: `calc(${theme.spacing(8)} + 1px)`,
  },
});

const DrawerHeader = styled("div")(({ theme }) => ({
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-end",
  padding: theme.spacing(0, 1),
  ...theme.mixins.toolbar,
}));

const Drawer = styled(MuiDrawer, {
  shouldForwardProp: (prop) => prop !== "open",
})(({ theme }) => ({
  width: drawerWidth,
  flexShrink: 0,
  whiteSpace: "nowrap",
  boxSizing: "border-box",
  variants: [
    {
      props: ({ open }) => open,
      style: {
        ...openedMixin(theme),
        "& .MuiDrawer-paper": openedMixin(theme),
      },
    },
    {
      props: ({ open }) => !open,
      style: {
        ...closedMixin(theme),
        "& .MuiDrawer-paper": closedMixin(theme),
      },
    },
  ],
}));

export default function SideNavBar() {
  const {
    threads,
    setThreads,
    currentThreadIndex,
    setCurrentThreadIndex,
    selectedItem,
    setSelectedItem,
  } = useThreads();
  const [open, setOpen] = React.useState(true);
  const [openDeleteDialog, setOpenDeleteDialog] = React.useState(false);
  const [threadToDelete, setThreadToDelete] = React.useState(null);
  const [anchorEl, setAnchorEl] = React.useState(null);
  const [openThreads, setOpenThreads] = React.useState(true);
  const [threadCount, setThreadCount] = React.useState();
  const currentUser = JSON.parse(localStorage.getItem("currentUser"));
  const [privateThreads, setPrivateThreads] = React.useState([]);
  const [workspaceThreads, setWorkspaceThreads] = React.useState([]);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (location.pathname.includes("/navbar/thread")) {
      setSelectedItem("Collections");
    }
  }, [location.pathname, setSelectedItem]);

  useEffect(() => {
    const loadInitialThreads = async () => {
      try {
        const currentUser = JSON.parse(localStorage.getItem("currentUser"));
        if (!currentUser || !currentUser.email) {
          console.warn("No logged-in user.");
          return;
        }

        const sessionRes = await fetch(
          `http://127.0.0.1:8000/chat/sessions?user_email=${encodeURIComponent(
            currentUser.email
          )}`
        );
        const sessionData = await sessionRes.json();
        let sessionDetails = sessionData.sessions;

        const loadedThreads = await Promise.all(
          sessionDetails.map(
            async ({ session_id, owner, collaborators }, index) => {
              try {
                const historyRes = await fetch(
                  `http://127.0.0.1:8000/chatHistory/${session_id}`
                );
                const historyData = await historyRes.json();
                const questions = historyData?.Questions || [];

                const messages = questions.map((q) => ({
                  question: q.Question,
                  response: q.response,
                  text: q.Question,
                  QuestionId: q.QuestionId,
                  history: (q.history || []).map((h) => ({
                    question: h.Question,
                    response: h.response,
                    timestamp: h.timestamp || "",
                  })),
                  currentVersion: 0,
                  isEdited: q.isEdited || false,
                  isFileUploaded: false,
                  fileName: "",
                  fileSize: "",
                  excelData: [],
                  sender: q.sender || "user",
                }));

                return {
                  sessionId: session_id,
                  name: `Thread ${index + 1}`,
                  pinned: false,
                  messages,
                  owner,
                  collaborators,
                  isWorkspace: collaborators && collaborators.length > 0, // ✨ MARK workspace
                };
              } catch (err) {
                console.error(
                  `Failed to load history for session ${session_id}:`,
                  err
                );
                return null;
              }
            }
          )
        );

        const privateOnly = loadedThreads.filter((t) => !t.isWorkspace);
        const workspaceOnly = loadedThreads.filter((t) => t.isWorkspace);

        setPrivateThreads(privateOnly);
        setWorkspaceThreads(workspaceOnly);

        setThreads([...privateOnly, ...workspaceOnly]);

        setCurrentThreadIndex(loadedThreads.length ? 0 : null);
        setThreadCount(loadedThreads.length);
      } catch (error) {
        console.error("Failed to load initial threads:", error);
      }
    };

    loadInitialThreads();
  }, [setCurrentThreadIndex, setThreads]);

  useEffect(() => {
    ThreadCount();
  });

  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    const sessionId = searchParams.get("id");

    if (sessionId && threads.length > 0) {
      setSelectedItem("Collections");

      const threadIndex = threads.findIndex((t) => t.sessionId === sessionId);
      if (threadIndex !== -1) {
        setCurrentThreadIndex(threadIndex);
      }
    }
  }, [location.search, setCurrentThreadIndex, setSelectedItem, threads]);

  const ThreadCount = async () => {
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/chat/sessions?user_email=${currentUser.email}`,
        {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        }
      );
      const json = await res.json();
      setThreadCount(json.count);
    } catch (error) {
      console.error("Error fetching uploaded files:", error);
    }
  };

  const handleListItemClick = (item) => {
    setSelectedItem(item);

    if (item === "My Files") {
      navigate("/navbar");
    } else if (item === "Workspace") {
      navigate("/navbar");
    } else if (item === "Data Sources") {
      navigate("/navbar");
    }
  };

  const handleNewThread = () => {
    const newThread = {
      sessionId: null,
      messages: [],
      name: `Thread ${threads.length + 1}`,
      pinned: false,
    };
    setThreads((prev) => [...prev, newThread]);
    setCurrentThreadIndex(threads.length);
  };

  const handleDeleteThread = async (index) => {
    try {
      const sessionId = threads[index]?.sessionId;
      if (sessionId) {
        await fetch(`http://127.0.0.1:8000/chat/${sessionId}`, {
          method: "DELETE",
        });
      }

      const updatedThreads = threads.filter((_, i) => i !== index);
      setThreads(updatedThreads);

      if (updatedThreads.length === 0) {
        setCurrentThreadIndex(-1);
      } else if (index <= currentThreadIndex) {
        setCurrentThreadIndex(Math.max(0, currentThreadIndex - 1));
      }
    } catch (error) {
      console.error("Failed to delete thread:", error);
    }
  };

  const handlePinThread = (index) => {
    setThreads((prev) =>
      prev.map((thread, i) =>
        i === index ? { ...thread, pinned: !thread.pinned } : thread
      )
    );
  };

  const handleRenameThread = (index) => {
    const newName = prompt("Enter new thread name:", threads[index].name);
    if (newName) {
      setThreads((prev) =>
        prev.map((thread, i) =>
          i === index ? { ...thread, name: newName } : thread
        )
      );
    }
  };

  const handleRightClick = (event, index) => {
    event.preventDefault();
    setThreadToDelete(index);
    setAnchorEl(event.currentTarget);
  };

  const handleCloseMenu = () => {
    setAnchorEl(null);
  };

  const renderContent = () => {
    switch (selectedItem) {
      case "Data Sources":
        return <Typography variant="h6">Data Sources Component</Typography>;
      case "Collections":
        return (
          <CollectionComponent
            threads={threads}
            setThreads={setThreads}
            currentThreadIndex={currentThreadIndex}
            setCurrentThreadIndex={setCurrentThreadIndex}
          />
        );
      case "My Files":
        return <ProjectComponent userEmail={currentUser} />;
      case "Workspace":
        return (
          <WorkspaceComponent
            threads={threads}
            setThreads={setThreads}
            currentThreadIndex={currentThreadIndex}
            setCurrentThreadIndex={setCurrentThreadIndex}
          />
        );
      case "Settings":
        return <Typography variant="h6">Settings Content</Typography>;
      default:
        return <Typography variant="h6">Select an item</Typography>;
    }
  };

  const handleDrawerOpen = () => {
    setOpen(true);
  };

  const handleDrawerClose = () => {
    setOpen(false);
  };

  return (
    <Box sx={{ display: "flex" }}>
      <CssBaseline />
      <AppTopToolBar sessionId={threads?.[currentThreadIndex]?.sessionId} />

      <Drawer className="Drawer" variant="permanent" open={open}>
        <Toolbar />
        <List>
          <Box sx={{ p: 1 }}>
            <Button
              variant="outlined"
              className="new-thread-container"
              fullWidth
              onClick={handleNewThread}
              sx={{ backgroundColor: "white", minWidth: "auto" }}
            >
              {open ? (
                <span className="new-thread-text">
                  {" "}
                  <FaPlus /> New Thread
                </span>
              ) : (
                <FaPlus />
              )}
            </Button>

            <Box sx={{ pt: 2 }}>
              <ListItem
                sx={{
                  justifyContent: "center",
                  ...(open
                    ? {
                        textAlign: "center",
                      }
                    : {
                        padding: "8px",
                        textAlign: "left",
                        "& .MuiListItemIcon-root": {
                          minWidth: "auto",
                        },
                      }),
                }}
                className="listItem"
                disablePadding
                onClick={() => setOpenThreads(!openThreads)}
              >
                {open ? (
                  <ListItemButton
                    className={`listItemButton ${open ? "open" : "closed"}`}
                  >
                    <ListItemIcon
                      className={`listItemIcon ${open ? "open" : "closed"}`}
                    >
                      <TiMessages className="thread-message-icon" />
                    </ListItemIcon>
                    <ListItemText
                      onClick={() => setOpenThreads(!openThreads)}
                      primary={`My Threads ${
                        threadCount > 0 ? `(${threadCount})` : ""
                      }`}
                    />
                    <IconButton size="small">
                      {openThreads ? (
                        <LuChevronsRight />
                      ) : (
                        <HiChevronDoubleDown />
                      )}
                    </IconButton>
                  </ListItemButton>
                ) : (
                  <ListItemIcon>
                    <TiMessages className="thread-message-icon" />
                  </ListItemIcon>
                )}
              </ListItem>

              <Collapse in={!openThreads} timeout="auto" unmountOnExit>
                <Box sx={{ overflowY: "auto", maxHeight: 250 }}>
                  <List sx={{ display: "block" }}>
                    {[
                      ...threads
                        .map((thread, index) => ({
                          ...thread,
                          originalIndex: index,
                        }))
                        .filter((thread) => thread.pinned),
                      ...threads
                        .map((thread, index) => ({
                          ...thread,
                          originalIndex: index,
                        }))
                        .filter((thread) => !thread.pinned)
                        .reverse(),
                    ].map((thread) => {
                      const index = thread.originalIndex;
                      return (
                        <ListItem
                          sx={{ overflowY: "auto", maxHeight: 240 }}
                          key={index}
                          disablePadding
                          secondaryAction={
                            open && (
                              <IconButton
                                className="button-threads-childs-3dots"
                                edge="end"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setThreadToDelete(index);
                                  setAnchorEl(e.currentTarget);
                                }}
                              >
                                <BsThreeDotsVertical className="threads-childs-3dots" />
                              </IconButton>
                            )
                          }
                          onContextMenu={(e) => handleRightClick(e, index)}
                        >
                          <ListItemButton
                            className={`threads-childs-text ${
                              open ? "open" : "close"
                            }`}
                            selected={index === currentThreadIndex}
                            onClick={() => {
                              setCurrentThreadIndex(index);
                              navigate(
                                `/navbar/thread?id=${threads[index]?.sessionId}`
                              );
                              setSelectedItem("Collections");
                             
                            }}
                          >
                            {thread.pinned && (
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handlePinThread(index);
                                }}
                                sx={{ mr: 1 }}
                              >
                                <SiPinboard />
                              </IconButton>
                            )}
                            <ListItemText
                              className="threads-childs-text-div"
                              // disablePadding
                              primary={
                                open ? (
                                  <>
                                    {!thread.pinned && (
                                      <SiPinboard
                                        style={{
                                          visibility: "hidden",
                                          marginRight: 6,
                                        }}
                                      />
                                    )}
                                    {thread.name}
                                  </>
                                ) : (
                                  index + 1
                                )
                              }
                            />
                          </ListItemButton>
                        </ListItem>
                      );
                    })}
                  </List>
                </Box>
              </Collapse>
            </Box>

            {["My Files", "Data Sources", "Workspace"].map((text) => {
              const selected = selectedItem === text;
              const topIcons =
                text === "Data Sources" ? (
                  <FaDatabase sx={{ color: "rgba(0, 0, 0, 0.54)" }} />
                ) : text === "Threads" ? (
                  <GrProjects className="collectionIcon" />
                ) : (
                  <LuFileSliders />
                );
              return (
                <ListItem
                  className="listItem"
                  key={text}
                  disablePadding
                  sx={{
                    background: selected ? "rgba(25, 118, 210, 0.12)" : "",
                    borderRadius: "4px",
                  }}
                >
                  <ListItemButton
                    className={`listItemButton ${open ? "open" : "closed"}`}
                    onClick={() => handleListItemClick(text)}
                  >
                    {!open ? (
                      <Tooltip title={text} placement="right">
                        <ListItemIcon
                          className={`listItemIcon ${open ? "open" : "closed"}`}
                          sx={{ color: selected ? "#151599" : "" }}
                        >
                          {topIcons}
                        </ListItemIcon>
                      </Tooltip>
                    ) : (
                      <ListItemIcon
                        className={`listItemIcon ${open ? "open" : "closed"}`}
                        sx={{ color: selected ? "#151599" : "" }}
                      >
                        {topIcons}
                      </ListItemIcon>
                    )}
                    <ListItemText
                      className={`listItemText ${
                        open ? "open" : "closed"
                      } ListText`}
                      primary={text}
                    />
                  </ListItemButton>
                </ListItem>
              );
            })}
          </Box>
        </List>

        <List>
          {["Settings", "Help"].map((text) => {
            const isHelp = text === "Help";
            const bottomIcons =
              text === "Settings" ? (
                <CiSettings className="settingIcon" />
              ) : (
                <IoHelpCircleOutline className="helpIcon" />
              );

            const bottomListItems = (
              <ListItemIcon
                className={`listItemIcon ${open ? "open" : "closed"}`}
              >
                {bottomIcons}{" "}
              </ListItemIcon>
            );

            const bottomListItemButton = (
              <ListItemButton
                className={`listItemButton ${open ? "open" : "closed"}`}
                onClick={() => handleListItemClick(text)}
              >
                {!open ? (
                  <Tooltip title={text} placement="right">
                    {bottomListItems}
                  </Tooltip>
                ) : (
                  bottomListItems
                )}
                <ListItemText
                  className={`listItemText ${
                    open ? "open" : "closed"
                  } ListText`}
                  primary={text}
                />
              </ListItemButton>
            );

            return (
              <ListItem
                sx={{ width: isHelp ? "50%" : "auto" }}
                key={text}
                disablePadding
              >
                {isHelp ? (
                  <>
                    <Typography component="div">
                      {bottomListItemButton}
                    </Typography>

                    <DrawerHeader
                      sx={{
                        minHeight: "0px !important",
                        transform: "translateX(5rem)",
                      }}
                    >
                      <Tooltip title="Close sideBar" placement="right">
                        <IconButton onClick={handleDrawerClose}>
                          <HiMiniChevronDoubleLeft />
                        </IconButton>
                      </Tooltip>
                    </DrawerHeader>
                  </>
                ) : (
                  bottomListItemButton
                )}
              </ListItem>
            );
          })}

          <Tooltip title="Open sideBar" placement="right">
            <IconButton
              aria-label="open drawer"
              edge="start"
              onClick={handleDrawerOpen}
              sx={[
                {
                  marginLeft: "12px",
                },
                open && { display: "none" },
              ]}
            >
              <LuChevronsRight />
            </IconButton>
          </Tooltip>
        </List>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3, overflow: "hidden" }}>
        {renderContent()}
      </Box>

      <Menu
        Paper={{
          elevation: 4,
          sx: {
            minWidth: 140,
            boxShadow: "0px 6px 20px rgba(0, 0, 0, 0.15)", // Soft shadow
            borderRadius: "10px",
            border: "1px solid rgba(43, 43, 43, 0.1)", // Softer border
            overflow: "visible",
            transition: "background-color 0.3s ease",
            color: (theme) =>
              theme.palette.mode === "dark"
                ? "rgb(237 236 236 / 74%) !important"
                : "#000 !important",
          },
        }}
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleCloseMenu}
      >
        <MenuItem
          onClick={() => {
            handleRenameThread(threadToDelete);
            handleCloseMenu();
          }}
        >
          <CreateOutlinedIcon sx={{ mr: 1 }} />
          Rename
        </MenuItem>
        <MenuItem
          onClick={() => {
            handlePinThread(threadToDelete);
            handleCloseMenu();
          }}
        >
          {threads[threadToDelete]?.pinned ? (
            <>
              <PushPinIcon sx={{ mr: 1 }} /> Unpin
            </>
          ) : (
            <>
              <PushPinOutlinedIcon sx={{ mr: 1 }} /> Pin
            </>
          )}
        </MenuItem>
        <MenuItem
          onClick={() => {
            setOpenDeleteDialog(true);
            handleCloseMenu();
          }}
        >
          <DeleteForeverOutlinedIcon sx={{ mr: 1, color: "#d60e0e" }} />
          Delete
        </MenuItem>
      </Menu>

      <Dialog
        open={openDeleteDialog}
        onClose={() => setOpenDeleteDialog(false)}
        PaperProps={{
          elevation: 4,
          sx: {
            mt: 1.5,
            py: "15px",
            px: "10px",
            minWidth: 300,
            width: 450,
            boxShadow: "0px 6px 20px rgba(0, 0, 0, 0.15)",
            borderRadius: "10px",
            border: "1px solid rgba(43, 43, 43, 0.1)",
            overflow: "visible",
            transition: "background-color 0.3s ease",
          },
        }}
      >
        <DialogTitle>Delete Thread?</DialogTitle>
        <Divider />
        <DialogContent>
          <Typography variant="body2" color="text.secondary">
            Are you sure you want to delete this Thread?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setOpenDeleteDialog(false)}
            sx={{
              px: "13px",
              border: "2px solid #e4e4e4",
              borderRadius: "20px",
              color: "black",
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={() => {
              handleDeleteThread(threadToDelete);
              setOpenDeleteDialog(false);
            }}
            sx={{
              px: "13px",
              border: "2px solid white",
              borderRadius: "20px",
              color: "white",
              backgroundColor: "#e02e2a",
              boxShadow: "0 0 0 2px #e02e2a",
            }}
            color="error"
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
