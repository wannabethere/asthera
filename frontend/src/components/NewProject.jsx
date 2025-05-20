// // SideBar

// import * as React from 'react';
// import {
//   Box, IconButton, List, ListItem, ListItemButton, ListItemIcon, ListItemText,
//   Toolbar, Tooltip, Typography, Button, Dialog, DialogActions, DialogContent, DialogTitle, Menu, MenuItem,
//   Collapse
// } from "@mui/material";
// import { styled } from '@mui/material/styles';
// import MuiDrawer from '@mui/material/Drawer';
// import CssBaseline from '@mui/material/CssBaseline';
// import { LuChevronsRight } from "react-icons/lu";
// import { HiMiniChevronDoubleLeft } from "react-icons/hi2";
// import { FaHome } from "react-icons/fa";
// import { GrProjects } from "react-icons/gr";
// import { LuFileSliders } from "react-icons/lu";
// import { CiSettings } from "react-icons/ci";
// import { IoHelpCircleOutline } from "react-icons/io5";
// import { FaPlus } from "react-icons/fa6";
// import { HiChevronDoubleDown } from "react-icons/hi2";
// import { TiMessages } from "react-icons/ti";
// import { SiPinboard } from "react-icons/si";
// import { BsThreeDotsVertical } from "react-icons/bs";
// import { Delete } from '@mui/icons-material'; // Import delete icon
// import '../../css/NavBar.css';

// import { AppTopToolBar } from './TopBar';
// import { HomeComponent } from '../navComponents/HomeComponent';
// import { ProjectComponent } from '../navComponents/ProjectsComponent';
// import { CollectionComponent } from '../navComponents/CollectionComponent';

// const drawerWidth = 240;

// const openedMixin = (theme) => ({
//   width: drawerWidth,
//   transition: theme.transitions.create('width', {
//     easing: theme.transitions.easing.sharp,
//     duration: theme.transitions.duration.enteringScreen,
//   }),
//   overflowX: 'hidden',
// });

// const closedMixin = (theme) => ({
//   transition: theme.transitions.create('width', {
//     easing: theme.transitions.easing.sharp,
//     duration: theme.transitions.duration.leavingScreen,
//   }),
//   overflowX: 'hidden',
//   width: `calc(${theme.spacing(7)} + 1px)`,
//   [theme.breakpoints.up('sm')]: {
//     width: `calc(${theme.spacing(8)} + 1px)`,
//   },
// });

// const DrawerHeader = styled('div')(({ theme }) => ({
//   display: 'flex',
//   alignItems: 'center',
//   justifyContent: 'flex-end',
//   padding: theme.spacing(0, 1),
//   // necessary for content to be below app bar
//   ...theme.mixins.toolbar,
// }));

// const Drawer = styled(MuiDrawer, { shouldForwardProp: (prop) => prop !== 'open' })(
//   ({ theme }) => ({
//     width: drawerWidth,
//     flexShrink: 0,
//     whiteSpace: 'nowrap',
//     boxSizing: 'border-box',
//     variants: [
//       {
//         props: ({ open }) => open,
//         style: {
//           ...openedMixin(theme),
//           '& .MuiDrawer-paper': openedMixin(theme),
//         },
//       },
//       {
//         props: ({ open }) => !open,
//         style: {
//           ...closedMixin(theme),
//           '& .MuiDrawer-paper': closedMixin(theme),
//         },
//       },
//     ],
//   }),
// );

// export default function SideNavBar() {
//   const [open, setOpen] = React.useState(true);
//   const [selectedItem, setSelectedItem] = React.useState('');
//   const [threads, setThreads] = React.useState([["Welcome to your first thread!"]]);
//   const [currentThreadIndex, setCurrentThreadIndex] = React.useState(0);
//   const [openDeleteDialog, setOpenDeleteDialog] = React.useState(false);
//   const [threadToDelete, setThreadToDelete] = React.useState(null);
//   const [anchorEl, setAnchorEl] = React.useState(null); // For right-click menu
//   const [openThreads, setOpenThreads] = React.useState(true);

//   // Handle clicking a menu item
//   const handleListItemClick = (item) => {
//     setSelectedItem(item);
//   };

//   // Create a new chat thread
//   const handleNewThread = () => {
//     const newThread = {
//       sessionId: null, // backend will generate this on first call
//       messages: [],
//     };
//     setThreads((prevThreads) => {
//       const newThreads = [...prevThreads, newThread];
//       setCurrentThreadIndex(newThreads.length - 1);
//       return newThreads;
//     });
//   };

//   const handleDeleteThread = async () => {
//     if (threadToDelete !== null) {
//       const sessionId = threads[threadToDelete]?.sessionId;

//       try {
//         // Call backend to delete session
//         await fetch(`http://127.0.0.1:8000/chat/${sessionId}`, {
//           method: "DELETE",
//         });

//         // 🧹 Update local state
//         const updatedThreads = threads.filter((_, index) => index !== threadToDelete);
//         setThreads(updatedThreads);

//         // Adjust selected thread index
//         if (updatedThreads.length === 0) {
//           setCurrentThreadIndex(null);
//         } else if (threadToDelete === updatedThreads.length) {
//           setCurrentThreadIndex(updatedThreads.length - 1);
//         } else {
//           setCurrentThreadIndex(threadToDelete);
//         }

//       } catch (error) {
//         console.error("Failed to delete session:", error);
//         // Optionally show error UI here
//       }

//       // Cleanup dialog state
//       setOpenDeleteDialog(false);
//       setThreadToDelete(null);
//     }
//   };

//   const handlePinThread = () => {
//     setThreads(prev =>
//       prev.map((thread, index) =>
//         index === threadToDelete ? { ...thread, pinned: !thread.pinned } : thread
//       )
//     );
//     handleCloseMenu();
//   };

//   const handleRenameThread = () => {
//     const newName = prompt("Enter a new name for the thread:");
//     if (newName) {
//       setThreads(prev =>
//         prev.map((thread, index) =>
//           index === threadToDelete ? { ...thread, name: newName } : thread
//         )
//       );
//     }
//     handleCloseMenu();
//   };

//   // Handle right-click on thread to open the delete menu
//   const handleRightClick = (event, index) => {
//     event.preventDefault(); // Prevent default context menu
//     setThreadToDelete(index);
//     setAnchorEl(event.currentTarget); // Open the menu at the right-click position
//   };

//   // Close the right-click delete menu
//   const handleCloseMenu = () => {
//     setAnchorEl(null);
//   };

//   // Render the selected component
//   const renderContent = () => {
//     switch (selectedItem) {
//       case 'Home':
//         return <HomeComponent />;
//       case 'Collections':
//         return (
//           <CollectionComponent
//             threads={threads}
//             setThreads={setThreads}
//             currentThreadIndex={currentThreadIndex}
//             setCurrentThreadIndex={setCurrentThreadIndex}
//             handleDeleteThread={handleDeleteThread}
//             setThreadToDelete={setThreadToDelete}
//             setOpenDeleteDialog={setOpenDeleteDialog}
//           />
//         );
//       case 'My Files':
//         return <ProjectComponent />;
//       case 'Settings':
//         return <Typography variant="h6">This is the Settings content.</Typography>;
//       default:
//         return <Typography variant="h6">Select an item from the menu.</Typography>;
//     }
//   };

//   const handleDrawerOpen = () => {
//     setOpen(true);
//   };

//   const handleDrawerClose = () => {
//     setOpen(false);
//   };

//   return (
//     <Box sx={{ display: 'flex' }}>
//       <CssBaseline />
//       <AppTopToolBar />

//       <Drawer className='Drawer' variant="permanent" open={open}>
//         <Toolbar />

//         <List>
//           <Box sx={{ p: 1 }}>
//             {selectedItem === 'Collections' && (
//               <>
//                 <Button variant="outlined" className='new-thread-container' fullWidth onClick={handleNewThread}>
//                   {open ? <span className='new-thread-text'><FaPlus /> New</span> : <FaPlus />}
//                 </Button>

//                 <Box sx={{ pt: 2 }}>
//                   <ListItem className='listItem' disablePadding
//                     button
//                     onClick={() => setOpenThreads(!openThreads)}
//                   >

//                     <ListItemButton sx={{ paddingLeft: '12px' }}>
//                       <ListItemIcon className={`listItemIcon ${open ? 'open' : 'closed'}`}>
//                         <TiMessages className='thread-message-icon' />
//                       </ListItemIcon>
//                       <ListItemText primary="My Threads" />
//                       <IconButton size="small">
//                         {openThreads ? <LuChevronsRight /> : <HiChevronDoubleDown />}
//                       </IconButton>
//                     </ListItemButton>
//                   </ListItem>

//                   <Collapse in={!openThreads} timeout="auto" unmountOnExit>
//                     <Box
//                       sx={{
//                         overflowY: 'auto',
//                         maxHeight: 250, // or adjust based on your layout
//                         pr: 1, // prevent scrollbar from overlapping text
//                       }}
//                     >
//                       <List>
//                         {[
//                           ...threads.map((thread, index) => ({ ...thread, originalIndex: index })).filter(thread => thread.pinned),
//                           ...threads.map((thread, index) => ({ ...thread, originalIndex: index })).filter(thread => !thread.pinned).reverse(),
//                         ].map((thread) => {
//                           const index = thread.originalIndex;
//                           return (
//                             <ListItem
//                               key={index}
//                               disablePadding
//                               secondaryAction={
//                                 <IconButton
//                                   edge="end"
//                                   onClick={(e) => {
//                                     e.stopPropagation(); // Prevent triggering thread open
//                                     setThreadToDelete(index);
//                                     setAnchorEl(e.currentTarget);
//                                   }}
//                                 >
//                                   <BsThreeDotsVertical />
//                                 </IconButton>
//                               }
//                               onContextMenu={(e) => handleRightClick(e, index)}
//                             >
//                               <ListItemButton
//                                 selected={index === currentThreadIndex}
//                                 onClick={() => setCurrentThreadIndex(index)}
//                               >
//                                 <ListItemText
//                                   primary={
//                                     open ? (
//                                       <>
//                                         {thread.pinned && (
//                                           <SiPinboard style={{ verticalAlign: 'middle', marginRight: 6 }} />
//                                         )}
//                                         {thread.name || `Thread ${index + 1}`}
//                                       </>
//                                     ) : (
//                                       index + 1
//                                     )
//                                   }
//                                 />
//                               </ListItemButton>
//                             </ListItem>
//                           );
//                         })}
//                       </List>
//                     </Box>
//                   </Collapse>
//                 </Box>
//               </>
//             )}
//           </Box>

//           {['Home', 'Collections', 'My Files',].map((text) => {
//             const selected = selectedItem === text;
//             const topIcons = text === 'Home' ? <FaHome /> : text === 'Collections' ?
//               <GrProjects className='collectionIcon' /> : <LuFileSliders />
//             const topListItems = <ListItemIcon className={`listItemIcon ${open ? 'open' : 'closed'}`}
//               sx={{ color: selected ? '#151599' : '' }} >
//               {topIcons}</ListItemIcon>
//             return (
//               <ListItem className='listItem' key={text} disablePadding
//                 sx={{ background: selected ? 'rgb(210 208 221);' : '', borderRadius: '4px' }}>
//                 <ListItemButton className={`listItemButton ${open ? 'open' : 'closed'}`}
//                   onClick={() => handleListItemClick(text)}>
//                   {
//                     !open ?
//                       <Tooltip title={text} placement="right">
//                         {topListItems}
//                       </Tooltip> :
//                       topListItems
//                   }
//                   <ListItemText className={`listItemText ${open ? 'open' : 'closed'} ListText`}
//                     primary={text} />
//                 </ListItemButton>
//               </ListItem>
//             )
//           }
//           )}
//         </List>

//         <List>
//           {['Settings', 'Help'].map((text) => {
//             const isHelp = text === 'Help';
//             const bottomIcons = text === 'Settings' ? <CiSettings className='settingIcon' /> : <IoHelpCircleOutline className='helpIcon' />

//             const bottomListItems = <ListItemIcon className={`listItemIcon ${open ? 'open' : 'closed'}`}>
//               {bottomIcons} </ListItemIcon>

//             const bottomListItemButton = <ListItemButton className={`listItemButton ${open ? 'open' : 'closed'}`}
//               onClick={() => handleListItemClick(text)}>
//               {

//                 !open ?
//                   <Tooltip title={text} placement='right'>
//                     {bottomListItems}
//                   </Tooltip> :
//                   bottomListItems
//               }
//               <ListItemText className={`listItemText ${open ? 'open' : 'closed'} ListText`}
//                 primary={text} />
//             </ListItemButton>

//             return (
//               <ListItem sx={{ width: isHelp ? '50%' : 'auto' }} key={text} disablePadding>
//                 {
//                   isHelp ?
//                     (<>
//                       <Typography component="div">
//                         {bottomListItemButton}
//                       </Typography>

//                       <DrawerHeader sx={{ minHeight: '0px !important', transform: 'translateX(5rem)' }}>
//                         <Tooltip title='Close sideBar' placement='right'>
//                           <IconButton onClick={handleDrawerClose}>
//                             <HiMiniChevronDoubleLeft />
//                           </IconButton>
//                         </Tooltip>
//                       </DrawerHeader>
//                     </>
//                     ) :
//                     bottomListItemButton
//                 }
//               </ListItem>
//             )
//           })}

//           <Tooltip title="Open sideBar" placement='right'>
//             <IconButton aria-label="open drawer" edge="start"
//               onClick={handleDrawerOpen}
//               sx={[
//                 {
//                   marginLeft: '12px',
//                 },
//                 open && { display: 'none' },
//               ]}>
//               <LuChevronsRight />
//             </IconButton>
//           </Tooltip>
//         </List>

//       </Drawer>

//       {/* Main Content */}
//       <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
//         <Toolbar />
//         {renderContent()}

//         {/* Delete Confirmation Dialog */}
//         <Dialog open={openDeleteDialog} onClose={() => setOpenDeleteDialog(false)}>
//           <DialogTitle>Confirm Deletion</DialogTitle>
//           <DialogContent>
//             <Typography>Are you sure you want to delete this thread?</Typography>
//           </DialogContent>
//           <DialogActions>
//             <Button onClick={() => setOpenDeleteDialog(false)} color="primary">
//               Cancel
//             </Button>
//             <Button onClick={handleDeleteThread} color="secondary">
//               Delete
//             </Button>
//           </DialogActions>
//         </Dialog>

//         {/* Right-click Delete Menu */}
//         <Menu
//           anchorEl={anchorEl}
//           open={Boolean(anchorEl)}
//           onClose={handleCloseMenu}
//         >
//           <MenuItem onClick={() => { setOpenDeleteDialog(true); handleCloseMenu(); }}>
//             Delete Thread
//           </MenuItem>
//           <MenuItem onClick={handlePinThread}>
//             {threads[threadToDelete]?.pinned ? 'Unpin Thread' : 'Pin Thread'}
//           </MenuItem>
//           <MenuItem onClick={handleRenameThread}>
//             Rename Thread
//           </MenuItem>
//         </Menu>
//       </Box>
//     </Box>
//   );
// }

// // App.js

// import './App.css';
// // import 'bootstrap/dist/css/bootstrap.min.css';
// import { Route, Routes, useLocation } from 'react-router-dom';
// import Login from './components/signInAndsignUp/Login'
// import SignUp from './components/signInAndsignUp/SignUp';
// import { useEffect } from 'react';
// import SideNavBar from './components/mainComponent/SideNavBar';
// import { SignUpSuccess } from './components/signInAndsignUp/SIgnUpSuccess';
// import CollectionComponent from './components/navComponents/CollectionComponent';

// function App() {

//   const location = useLocation()

//   useEffect(() => {
//     const loc = location.pathname;
//     const pathNames = ['/', '/signup', '/signupSucess'];

//     const isTrue = pathNames.includes(loc)
//     if (isTrue) {
//       document.body.style.background = 'linear-gradient(110deg,  #d9b878, #6f4f43, #0d2528)';
//       document.body.style.backgroundSize = 'cover';
//       document.body.style.backgroundRepeat = 'no-repeat';
//       document.body.style.backgroundAttachment = 'fixed';
//     } else {
//       document.body.style.background = '';
//     }
//   }, [location])

//   return (

//     <div className="App">
//       <Routes>
//         <Route path='' element={<Login />}></Route>
//         <Route path='signup' element={<SignUp />}></Route>
//         <Route path='/signupSucess' element={<SignUpSuccess />}></Route>
//         <Route path='/navbar' element={<SideNavBar />}></Route>
//         {/* <Route path='/pages/components' element={<CollectionComponent />}></Route> */}
//       </Routes>
//     </div>
//   );
// }

// // export default App;

// // CollectionComponent

// import React, { useState, useRef, useEffect, useMemo } from "react";
// import {
//   Box,
//   IconButton,
//   List,
//   ListItem,
//   ListItemText,
//   Tooltip,
//   Typography,
//   Button,
//   Divider
// } from "@mui/material";
// import { styled } from "@mui/material/styles";
// import { HiMiniChevronDoubleLeft } from "react-icons/hi2";
// import { LuChevronsRight } from "react-icons/lu";
// import { IoMdAttach, IoIosSend } from "react-icons/io";
// import { CiEdit } from "react-icons/ci";
// import { IoMdCopy } from "react-icons/io";
// import { BeatLoader } from "react-spinners";
// import { FaRegSave } from "react-icons/fa";
// import '../../css/sentBox.css';
// import { AgGridReact } from "ag-grid-react";
// import {
//   AllCommunityModule, ModuleRegistry, colorSchemeDarkBlue, themeQuartz
// } from "ag-grid-community";
// import Plot from 'react-plotly.js';
// import Tab from '@mui/material/Tab';
// import TabContext from '@mui/lab/TabContext';
// import TabList from '@mui/lab/TabList';
// import TabPanel from '@mui/lab/TabPanel';
// import { FaFileAlt } from "react-icons/fa";
// import { IoCloseCircleOutline } from "react-icons/io5";

// import * as XLSX from 'xlsx';

// // const drawerWidth = 300;

// // const openedMixin = (theme) => ({
// //   width: drawerWidth,
// //   transition: theme.transitions.create("width", {
// //     easing: theme.transitions.easing.sharp,
// //     duration: theme.transitions.duration.enteringScreen,
// //   }),
// //   overflowX: "hidden",
// // });

// // const closedMixin = (theme) => ({
// //   transition: theme.transitions.create("width", {
// //     easing: theme.transitions.easing.sharp,
// //     duration: theme.transitions.duration.leavingScreen,
// //   }),
// //   overflowX: "hidden",
// //   width: 0,
// // });

// // const Drawer = styled("div")(({ theme, open }) => ({
// //   width: drawerWidth,
// //   position: "absolute",
// //   right: 0,
// //   top: 0,
// //   height: "100vh",
// //   transition: "width 0.3s ease-in-out",
// //   overflow: "hidden",
// //   ...(open ? openedMixin(theme) : closedMixin(theme)),
// // }));

// export const CollectionComponent = ({ threads, setThreads, currentThreadIndex, setCurrentThreadIndex }) => {
//   const [inputValue, setInputValue] = useState("");
//   const [loading, setLoading] = useState(false);
//   const [historyOpen, setHistoryOpen] = useState(false);
//   const currentThread = threads?.[currentThreadIndex]?.messages || [];
//   const [conversations, setConversations] = useState(currentThread);
//   const [sessionId, setSessionId] = useState(currentThread.sessionId);
//   const messageRefs = useRef([]);
//   const fileInputRef = useRef(null);
//   const [fileNameAndSize, setFileNameAndSize] = useState({
//     fileName: '',
//     fileSize: '',
//     isFileExists: false
//   });
//   const [completedFileDetails, setcompletedFileDetails] = useState({});
//   const [agGridLoad, setAgGridLoad] = useState(false)

//   useEffect(() => {
//     const validMessages = threads?.[currentThreadIndex]?.messages?.filter(
//       (msg) => msg.question?.trim() || msg.response?.trim()
//     ) || [];
//     setConversations(validMessages);
//   }, [currentThreadIndex, threads]);

//   useEffect(() => {
//     messageRefs.current = messageRefs.current.slice(0, conversations.length);
//   }, [conversations]);

//   const handleOpenDialogPicker = () => {
//     if (fileInputRef.current) {
//       fileInputRef.current.click();
//     }
//   }

//   const handleFileUpload = (e) => {
//     const file = e.target.files[0];
//     setcompletedFileDetails({ file: e.target.files[0] })

//     if (!file) return;
//     setFileNameAndSize({
//       fileName: file.name,
//       fileSize: `${(file.size / 1024).toFixed(2)} KB`,
//       isFileExists: true
//     });
//   };

//   const handleFileDiscard = () => {
//     setFileNameAndSize({
//       fileName: '',
//       fileSize: '',
//       isFileExists: false
//     });
//     setcompletedFileDetails({});
//   }

//   const analyzeExcelData = async (file, sessionId) => {
//     try {

//       const jsonData = await new Promise((resolve, reject) => {
//         const reader = new FileReader();

//         reader.onload = (e) => {
//           try {
//             const data = new Uint8Array(e.target.result);
//             const workbook = XLSX.read(data, { type: 'array' });
//             const jsonData = XLSX.utils.sheet_to_json(workbook.Sheets[workbook.SheetNames[0]]);
//             resolve(jsonData);
//           } catch (error) {
//             reject(error);
//           }
//         };

//         reader.onerror = reject;
//         reader.readAsArrayBuffer(file);
//       });

//       const dataString = JSON.stringify(jsonData.slice(0, 10));

//       const user_input = `Excel Data (first 10 rows): ${dataString}\n\nPlease provide a brief overview of this data including:
//   1. Summary of the file
//   2. Key columns and their purposes
//   3. Any immediate observations`;

//       const endpoint = sessionId ? `/chat/${sessionId}/continue` : `/chat/start`;

//       const response = await fetch(`http://127.0.0.1:8000${endpoint}`, {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify({ user_input }),
//       });

//       const data = await response.json();

//       return { analysis: data.response, excelJson: jsonData, sessionId: data.session_id || sessionId };
//     } catch (error) {
//       console.error("Error analyzing Excel data:", error);
//       return { analysis: "Error analyzing the Excel file.", excelJson: [], sessionId };
//     }
//   };

//   const handleSendMessage = async () => {
//     if (!inputValue.trim() && !fileNameAndSize?.isFileExists) {
//       console.log('Please provide text or upload a file to submit.');
//       return;
//     }

//     setAgGridLoad(true);

//     const userPrompt = inputValue.trim();
//     const fallbackPrompt = ".";

//     const newConversation = {
//       question: userPrompt || fallbackPrompt,
//       response: "",
//       history: [],
//       currentVersion: 0,
//       isEdited: false,
//       isFileUploaded: !!completedFileDetails?.file,
//       fileName: completedFileDetails?.file?.name || "",
//       fileSize: completedFileDetails?.file
//         ? `${(completedFileDetails.file.size / 1024).toFixed(2)} KB`
//         : "",
//       excelData: [],
//       text: userPrompt || fallbackPrompt,
//       sender: "user",
//     };

//     const updated = [...conversations, newConversation];
//     setConversations(updated);
//     setInputValue("");
//     setLoading(true);

//     try {
//       let fullResponse;
//       const currentThread = threads[currentThreadIndex];
//       let currentSessionId = currentThread?.sessionId;

//       if (completedFileDetails?.file) {
//         const { analysis, excelJson, sessionId: newSessionId } = await analyzeExcelData(completedFileDetails.file, currentSessionId);
//         setAgGridLoad(false);
//         const withExcel = [...updated];
//         withExcel[withExcel.length - 1].excelData = excelJson;
//         setConversations(withExcel);

//         const excelPrompt = `
//   You are answering questions about an Excel file. First provide a brief overview of the file, then answer the user's question. Here's the analysis you already did:
//   ${analysis}

//   The user has asked:
//   ${userPrompt || fallbackPrompt}
//   1. Key Trends
//   2. Key columns and their purposes
//   3. Data Issues
//   4. Any Suggestions needed

//   Additionally, provide 3 or 4 recommended analysis questions based on this data.
//   These should be questions that a data analyst would typically ask when analyzing this type of data.
//   `;

//         const endpoint = newSessionId ? `/chat/${newSessionId}/continue` : "/chat/start";
//         const response = await fetch(`http://127.0.0.1:8000${endpoint}`, {
//           method: "POST",
//           headers: { "Content-Type": "application/json" },
//           body: JSON.stringify({ user_input: excelPrompt }),
//         });

//         const data = await response.json();

//         fullResponse = withExcel.map((msg, i) =>
//           i === withExcel.length - 1
//             ? { ...msg, response: formatAIResponse(data.response) }
//             : msg
//         );

//         updateThread(fullResponse, newSessionId || data.session_id);

//         setFileNameAndSize({ fileName: '', fileSize: '', isFileExists: false });
//         setcompletedFileDetails({});
//       } else {
//         const endpoint = currentSessionId ? `/chat/${currentSessionId}/continue` : "/chat/start";

//         const response = await fetch(`http://127.0.0.1:8000${endpoint}`, {
//           method: "POST",
//           headers: { "Content-Type": "application/json" },
//           body: JSON.stringify({ user_input: userPrompt || fallbackPrompt }),
//         });

//         const data = await response.json();

//         fullResponse = updated.map((msg, i) =>
//           i === updated.length - 1
//             ? { ...msg, response: formatAIResponse(data.response) }
//             : msg
//         );

//         updateThread(fullResponse, currentSessionId || data.session_id);
//       }
//     } catch (error) {
//       console.error("Error:", error);
//       const errored = updated.map((msg, i) =>
//         i === updated.length - 1
//           ? { ...msg, response: "Error fetching response." }
//           : msg
//       );
//       setConversations(errored);
//       updateThread(errored);
//     }

//     setLoading(false);
//   };

//   const updateThread = (updatedMessages, newSessionId = null) => {
//     const all = [...threads];
//     const existingThread = all[currentThreadIndex] || { messages: [], sessionId: null };
//     all[currentThreadIndex] = {
//       ...existingThread,
//       messages: updatedMessages,
//       sessionId: newSessionId || existingThread.sessionId
//     };
//     setThreads(all);
//   };

//   const scrollToMessage = (index) => {
//     if (messageRefs.current[index]) {
//       messageRefs.current[index].scrollIntoView({ behavior: "smooth", block: "start" });
//     }
//   };

//   return (
//     <Box sx={{ display: "flex", height: "85vh" }}>
//       <Box sx={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", position: "relative" }}>
//         {/* Scrollable chat content */}
//         <Box
//           className="chatMessages"
//           sx={{
//             flex: 1,
//             overflowY: "auto",
//             padding: 2,
//             paddingBottom: "100px", // space for the fixed input box
//           }}
//         >
//           {conversations.map((conversation, index) => (
//             <div key={index} ref={(el) => (messageRefs.current[index] = el)} style={{ width: "100%" }}>
//               <EditCopySave
//                 conversation={conversation}
//                 setConversations={setConversations}
//                 currentIndex={index}
//                 updateThread={updateThread}
//                 fileNameAndSize={fileNameAndSize}
//                 // excelData={excelData}
//                 AllCommunityModule={AllCommunityModule}
//                 sessionId={sessionId}
//                 agGridLoad={agGridLoad}
//               />
//             </div>
//           ))}
//         </Box>

//         {/* Fixed input box */}
//         <Box
//           className="sentBox-container"
//           sx={{
//             bottom: 0,
//             width: "80%",
//             backgroundColor: "#fff",
//             borderTop: "1px solid #ddd",
//             padding: 2,
//             display: "flex",
//             alignItems: "center",
//             gap: 1,
//           }}
//         >
//           <Box>
//             {fileNameAndSize.isFileExists && (
//               <Box className='upload-file-container' sx={{ display: "flex", borderRadius: "20px" }}>
//                 <Box className='file-icon'><FaFileAlt /></Box>
//                 <Box sx={{ margin: "8px" }}>
//                   <Typography>{fileNameAndSize.fileName}</Typography>
//                   <Typography>{fileNameAndSize.fileSize}</Typography>
//                 </Box>
//                 <IoCloseCircleOutline onClick={handleFileDiscard} />
//               </Box>
//             )}
//           </Box>

//           <Box className="sentBox-container_text">
//             <Box>
//               <IoMdAttach className="attachIcon" onClick={handleOpenDialogPicker} />
//               <input
//                 type="file"
//                 accept=".xlsx, .xls, .csv"
//                 ref={fileInputRef}
//                 onChange={handleFileUpload}
//                 style={{ display: "none" }}
//               />
//             </Box>

//             <Box className="textarea-container">
//               <textarea
//                 className="textareaField"
//                 value={inputValue}
//                 onChange={(e) => setInputValue(e.target.value)}
//                 placeholder="Type a message..."
//                 onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
//               />
//             </Box>

//             <Box
//               onClick={handleSendMessage}
//               disabled={loading || !inputValue.trim()}
//               className="send-button"
//             >
//               <IoIosSend className="sentIcon" />
//             </Box>
//           </Box>
//         </Box>
//       </Box>

//       <Box
//         sx={{
//           width: historyOpen ? drawerWidth : 0,
//           borderRight: "1px solid #ddd",
//           p: 2,
//           transition: "width 0.3s ease-in-out",
//           overflow: "hidden",
//         }}
//       >
//         <Box sx={{ p: 2, height: "100%", overflowY: "auto" }}>
//           <Typography variant="h6">Chat History</Typography>
//           {conversations.length > 0 ? (
//             <List>
//               {conversations.filter((msg) => msg.sender === "user").map((msg, idx) => (
//                 <ListItem key={idx} button onClick={() => scrollToMessage(idx)}>
//                   <ListItemText primary={`You: ${msg.text}`} />
//                 </ListItem>
//               ))}
//             </List>
//           ) : (
//             <Typography variant="body2" sx={{ mt: 2 }}>No history for this thread.</Typography>
//           )}
//         </Box>
//       </Box>

//       <Tooltip title={historyOpen ? "Close History" : "Show History"}>
//         <IconButton
//           onClick={() => setHistoryOpen(!historyOpen)}
//           sx={{
//             position: "fixed",
//             top: "50%",
//             right: historyOpen ? `${drawerWidth + 10}px` : "10px",
//             transform: "translateY(-50%)",
//             transition: "right 0.3s ease-in-out",
//             backgroundColor: "#fff",
//             borderRadius: "50%",
//             boxShadow: "0px 4px 6px rgba(0,0,0,0.1)",
//             zIndex: 1300,
//           }}
//         >
//           {historyOpen ? <HiMiniChevronDoubleLeft /> : <LuChevronsRight />}
//         </IconButton>
//       </Tooltip>
//     </Box>
//   );
// };

// const formatAIResponse = (text) => {
//   if (!text) return '';
//   return text
//     .replace(/</g, '&lt;') // sanitize any HTML
//     .replace(/>/g, '&gt;')
//     .replace(/\n{2,}/g, '\n') // collapse multiple newlines
//     .replace(/\n/g, '<br>')   // convert newlines to <br>
//     .replace(/^\d+\.\s/gm, match => `<br><strong>${match.trim()}</strong>`) // highlight numbered items
//     .replace(/(?<=\\s)-\\s/g, '<br>• '); // handle bullets
// };

// const EditCopySave = ({ conversation, setConversations, currentIndex, updateThread, sessionId, agGridLoad }) => {
//   const [isCopied, setIsCopied] = useState(false);
//   const [isEdit, setIsEdit] = useState(false);
//   const [editValue, setEditValue] = useState(conversation.question);
//   const [colDefs, setColDefs] = useState([]);

//   ModuleRegistry.registerModules([AllCommunityModule]);
//   const rowSelection = useMemo(() => {
//     return {
//       mode: 'multiRow'
//     };
//   }, []);

//   const generateColumnDefs = (data) => {
//     if (!data || data.length === 0) return [];

//     const headers = Object.keys(data[0]);
//     return headers.map(header => ({
//       field: header,
//       headerName: header.toUpperCase().replace(/_/g, ' '),
//       sortable: true,
//       filter: true,
//       editable: true
//     }));
//   };

//   useEffect(() => {
//     if (Array.isArray(conversation?.excelData) && conversation.excelData.length > 0) {
//       setColDefs(generateColumnDefs(conversation.excelData));
//     }
//   }, [conversation.excelData]);

//   const handleCopy = () => {
//     navigator.clipboard.writeText(conversation.response || "")
//       .then(() => {
//         setIsCopied(true);
//         setTimeout(() => setIsCopied(false), 2000);
//       })
//       .catch(console.error);
//   };

//   const handleEdit = () => {
//     setIsEdit(true);
//     setEditValue(conversation.question);
//   };

//   const handleUpdateText = async () => {
//     if (!editValue.trim()) return;

//     const newHistory = [
//       {
//         question: conversation.question,
//         response: conversation.response,
//         timestamp: new Date().toISOString(),
//       },
//       ...(conversation.history || []),
//     ];

//     setConversations(prev => {
//       const updated = [...prev];
//       updated[currentIndex] = {
//         ...updated[currentIndex],
//         question: editValue,
//         text: editValue,
//         response: "",
//         history: newHistory,
//         currentVersion: 0,
//         isEdited: true,
//       };
//       updateThread(updated);
//       return updated;
//     });

//     try {
//       const response = await fetch(`http://127.0.0.1:8000/chat/${sessionId}/continue`, {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify({ user_input: editValue }),
//       });

//       const data = await response.json();

//       setConversations(prev => {
//         const updated = [...prev];
//         updated[currentIndex].response = formatAIResponse(data.response);
//         updateThread(updated);
//         return updated;
//       });
//     } catch (error) {
//       console.error("Error:", error);
//       setConversations(prev => {
//         const updated = [...prev];
//         updated[currentIndex].response = "Error fetching response.";
//         updateThread(updated);
//         return updated;
//       });
//     }

//     setIsEdit(false);
//   };

//   const handleCancel = () => {
//     setIsEdit(false);
//     setEditValue(conversation.question);
//   };

//   const handleVersionChange = (direction) => {
//     setConversations(prev => {
//       const updated = [...prev];
//       const conv = updated[currentIndex];
//       const newVer = conv.currentVersion + direction;
//       if (newVer >= 0 && newVer <= (conv.history?.length || 0)) {
//         conv.currentVersion = newVer;
//       }
//       updateThread(updated);
//       return updated;
//     });
//   };

//   const getCurrentVersion = () => {
//     if (
//       !conversation.history ||
//       conversation.history.length === 0 ||
//       conversation.currentVersion === 0
//     ) {
//       return {
//         question: conversation.question,
//         response: conversation.response,
//       };
//     }

//     return conversation.history[conversation.currentVersion - 1];
//   };

//   const currentData = getCurrentVersion();
//   const showVersionControls = conversation.isEdited && (conversation.history?.length || 0) > 0;

//   return (
//     <>
//       {/* User Question (right side) */}
//       <div
//         className="chateachMessage"
//         style={{
//           backgroundColor: "#daf8cb",
//           maxWidth: isEdit ? "60%" : "80%",
//           minWidth: isEdit ? "60%" : "auto",
//           width: 'fit-content',
//           marginLeft: 'auto',
//           marginBottom: '8px'
//         }}
//       >
//         {isEdit ? (
//           <>
//             <textarea
//               className="textareaField"
//               value={editValue}
//               onChange={(e) => setEditValue(e.target.value)}
//               style={{ width: '100%', minHeight: '60px' }}
//             />
//             <Box style={{ display: "flex", gap: "10px", marginTop: "5px" }}>
//               <Button onClick={handleUpdateText} variant="contained" style={{ backgroundColor: '#4CAF50', color: 'white' }}>Update</Button>
//               <Button onClick={handleCancel} variant="contained" style={{ backgroundColor: '#f44336', color: 'white' }}>Cancel</Button>
//             </Box>
//           </>
//         ) : (
//           <div className="question">
//             {conversation.isFileUploaded && (
//               <Box className='upload-file-container' sx={{ display: "flex", borderRadius: "20px" }}>
//                 <Box className='file-icon'><FaFileAlt /></Box>
//                 <Box sx={{ margin: "8px" }}>
//                   <Typography>{conversation.fileName}</Typography>
//                   <Typography>{conversation.fileSize}</Typography>
//                 </Box>
//               </Box>
//             )}
//             {currentData.question}
//             {showVersionControls && (
//               <div style={{ fontSize: "12px", color: "gray", marginTop: "5px" }}>
//                 <button
//                   onClick={() => handleVersionChange(-1)}
//                   disabled={conversation.currentVersion === 0}
//                   style={{ background: 'none', border: 'none', cursor: 'pointer' }}
//                 >
//                   ◀️
//                 </button>
//                 <span style={{ margin: '0 8px' }}>
//                   {conversation.currentVersion + 1} / {(conversation.history?.length || 0) + 1}
//                 </span>
//                 <button
//                   onClick={() => handleVersionChange(1)}
//                   disabled={conversation.currentVersion === (conversation.history?.length || 0)}
//                   style={{ background: 'none', border: 'none', cursor: 'pointer' }}
//                 >
//                   ▶️
//                 </button>
//               </div>
//             )}
//           </div>
//         )}
//       </div>

//       {/* Action buttons (right side with question) */}
//       <Box style={{
//         alignSelf: "flex-end",
//         display: "flex",
//         gap: "10px",
//         marginBottom: '8px',
//         justifyContent: 'flex-end'
//       }}>
//         <CiEdit onClick={handleEdit} style={{ cursor: "pointer", fontSize: "20px" }} title="Edit question" />
//         <Tooltip title={isCopied ? "Copied!" : "Copy"} placement="bottom">
//           <IoMdCopy onClick={handleCopy} style={{ cursor: "pointer", color: isCopied ? "green" : "black", fontSize: "20px" }} />
//         </Tooltip>
//       </Box>

//       {/* Bot Response (left side) */}

//       {
//         conversation.isFileUploaded && (
//           <div style={{ height: '500px', width: '100%', marginBottom: "20px" }}>
//             <AgGridReact className="ag-theme-quartz"
//               // theme={myTheme}
//               rowSelection={rowSelection}
//               rowData={conversation.excelData}
//               columnDefs={colDefs}
//             />
//           </div>
//         )}

//       {conversation.isFileUploaded && <GraphPlotlyUI conversation={conversation} />}

//       {!currentData.response ? <BeatLoader size={10} /> : (
//         <div
//           className="chateachMessage"
//           style={{
//             backgroundColor: "#f1f1f1",
//             maxWidth: isEdit ? "60%" : "80%",
//             minWidth: isEdit ? "60%" : "auto",
//             width: "fit-content",
//             marginBottom: "8px",
//             padding: "10px",
//             borderRadius: "8px",
//             lineHeight: 1.6,
//           }}
//           dangerouslySetInnerHTML={{ __html: currentData.response }}
//         />
//       )}
//     </>
//   );
// };

// const GraphPlotlyUI = ({ conversation }) => {
//   const [tabValue, setTabValue] = useState('1');
//   const [graphType, setGraphType] = useState('bar');
//   const [barMode, setBarMode] = useState(null);
//   const [orientation, setOreintation] = useState('');
//   const [mode, setMode] = useState('')
//   const [fill, setFill] = useState('')
//   const [selectValue, setSelectValue] = useState('scatter');

//   // x-axis
//   const [xaxisColumn, setXaxisColumn] = useState('Order ID');

//   // y-axis
//   const [yaxisColoumn, setYaxisColoumn] = useState('Customer ID');

//   const handleGraphTypeChange = (event) => {
//     const selectedType = event.target.value;
//     const extractGraphType = selectedType.split('_')[0];
//     setSelectValue(selectedType);

//     setGraphType(extractGraphType);

//     if (extractGraphType === 'bar') {
//       const selectedBarMode = event.target.selectedOptions[0].getAttribute('data-barmode');
//       const selectedOreintation = event.target.selectedOptions[0].getAttribute('data-orientation');
//       setOreintation(selectedOreintation)
//       setBarMode(selectedBarMode);
//     }
//     else if (extractGraphType === 'scatter') {
//       const selectedFill = event.target.selectedOptions[0].getAttribute('data-fill');
//       const selectedMode = event.target.selectedOptions[0].getAttribute('data-mode');
//       setFill(selectedFill);
//       setMode(selectedMode);
//     }
//     else {
//       setBarMode(null);
//       setFill(null);
//     }
//   };

//   return (<>
//     <div style={{ width: '100%', height: 460, border: '1px solid #dfdada' }}>
//       <Box sx={{ display: 'flex', }}>
//         <Box sx={{ width: '30%', marginTop: '2%', marginLeft: '1%', minWidth: '300px' }}>

//           <Box>
//             <label htmlFor="graphType">Type : </label>
//             <select
//               id="graphType"
//               value={selectValue}
//               onChange={handleGraphTypeChange}
//             >
//               <option value="bar_group_coloumn" data-barmode="group" data-orientation=''>Grouped Coloumn</option>
//               <option value="bar_stacked_coloumn" data-barmode="stack" data-orientation=''>Stacked Coloumn</option>
//               {/* <Divider /> */}
//               <option value="scatter_multiple_line_chart" data-fill='' data-mode='lines+markers'>Line Chart</option>
//               <option value="scatter_area_line_chart" data-fill='tozeroy' data-mode='lines+markers'>Stacked Area</option>
//               <option value="scatter_markers_line_chart" data-fill='' data-mode='markers'>Scattered Plot</option>
//               {/* <Divider /> */}
//               <option value="bar_group" data-barmode="group" data-orientation='h'>Grouped Bar</option>
//               <option value="bar_stacked" data-barmode="stack" data-orientation='h'>Stacked Bar</option>
//               <option value="histogram">Histogram Bar</option>
//               {/* <Divider /> */}
//               <option value="pie">Pie Chart</option>
//             </select>
//           </Box>

//           {/* <Toolbar /> */}
//           <FilterationForXAxis rowData={conversation.excelData} xaxisColumn={xaxisColumn} setXaxisColumn={setXaxisColumn} />

//           {/* <Toolbar /> */}

//           <FilterationForYAxis rowData={conversation.excelData} yaxisColoumn={yaxisColoumn} setYaxisColoumn={setYaxisColoumn} />
//         </Box>

//         <Box style={{ borderLeft: '1px solid #dfdada', width: '100%' }}>
//           {graphType === 'histogram' && <HistogramComponent />}

//           {graphType === 'pie' && <PieComponent />}

//           {graphType !== 'histogram' && graphType !== 'pie' && (
//             <Plot
//               data={getDynamicGraphData(xaxisColumn, yaxisColoumn, conversation.excelData, graphType, orientation, mode, fill)} // Dynamic data based on X and Y axis
//               layout={{
//                 title: `Dynamic ${graphType.charAt(0).toUpperCase() + graphType.slice(1)} Graph`,
//                 barmode: barMode,
//                 xaxis: {
//                   title: {
//                     text: xaxisColumn,
//                     width: '10px'
//                   }
//                 },
//                 yaxis: {
//                   title: {
//                     text: yaxisColoumn
//                   }
//                 }
//               }}
//               config={{
//                 responsive: true,
//               }}
//               style={{ width: '100%' }}
//             />
//           )}
//         </Box>
//       </Box>
//     </div>
//   </>)
// }

// const getDynamicGraphData = (xaxisColumn, yaxisColoumn, rowData, graphType, orientation, mode, fill) => {
//   const xData = rowData.map(item => item[xaxisColumn]);
//   const yData = rowData.map(item => item[yaxisColoumn]);

//   const colors = ['#FF5733', '#33FF57', '#3357FF', '#F333FF', '#FF3356', '#FF8C00', '#00BFFF'];
//   const colorArray = rowData.map((_, index) => colors[index % colors.length]);

//   return [
//     {
//       x: xData,
//       y: yData,
//       type: graphType,
//       orientation: orientation,
//       mode: mode,
//       fill: fill,
//       marker: {
//         size: 12,
//         color: colorArray
//       },
//     }
//   ];
// };

// const HistogramComponent = () => {
//   const [dataHistogram, setDataHistogram] = useState([12, 14, 16, 18, 12, 20, 18, 17, 14, 19, 20, 22, 24, 18, 17, 14]);

//   return (
//     <Plot
//       data={[
//         {
//           type: 'histogram',
//           x: dataHistogram,
//           nbinsx: 10,
//           name: 'Sample Data',
//           marker: {
//             color: 'rgba(50, 171, 96, 0.6)',
//           },
//         },
//       ]}
//       layout={{
//         width: '100%',
//         height: '100%',
//         bargroupgap: 0.2,
//         title: {
//           text: "Sampled Results"
//         },
//         xaxis: {
//           title: {
//             text: "Value"
//           }
//         },
//         yaxis: {
//           title: {
//             text: "Count"
//           }
//         }
//       }}
//     />
//   )
// }

// const PieComponent = () => {
//   return (
//     <Plot
//       data={[
//         {
//           type: 'pie',
//           labels: ['A', 'B', 'C'],
//           values: [10, 20, 30],
//           hoverinfo: 'label+percent',
//           // textinfo: 'label+percent',
//         },
//       ]}
//       layout={{
//         width: '100%',
//         height: '100%',
//         title: {
//           text: "Pie Results"
//         },
//         showlegend: true,
//       }}
//     />
//   );
// };

// const FilterationForXAxis = ({ rowData, xaxisColumn, setXaxisColumn }) => {
//   return (
//     <>
//       <Box sx={{ mt: 2, display: 'flex', alignItems: 'baseline' }}>
//         <label>X-axis : </label>
//         <FilterationForAxis
//           rowData={rowData}
//           axisColumn={xaxisColumn}
//           setAxisColumn={setXaxisColumn}
//           axisType="x"
//           SetScaleType={SetScaleTypeForX} // Pass X-axis scale type function
//         />
//       </Box>

//     </>
//   );
// };

// const FilterationForYAxis = ({ rowData, yaxisColoumn, setYaxisColoumn }) => {
//   return (
//     <>
//       <Box sx={{ mt: 2, display: 'flex', alignItems: 'baseline' }}>
//         <label>Y-axis : </label>
//         <FilterationForAxis
//           rowData={rowData}
//           axisColumn={yaxisColoumn}
//           setAxisColumn={setYaxisColoumn}
//           axisType="y"
//           SetScaleType={SetAggregateTypeForY} // Pass Y-axis scale type function
//         />
//       </Box>
//     </>
//   );
// };

// const FilterationForAxis = ({ rowData, axisColumn, setAxisColumn, axisType, SetScaleType }) => {
//   const columnTypes = {};
//   if (rowData.length === 0) return null;

//   Object.keys(rowData[0]).forEach((key) => {
//     const value = rowData[0][key];
//     if (typeof value === "number") {
//       columnTypes[key] = "numeric";
//     } else if (typeof value === "boolean") {
//       columnTypes[key] = "boolean";
//     } else if (!isNaN(Date.parse(value))) {
//       columnTypes[key] = "datetime";
//     } else {
//       columnTypes[key] = "string";
//     }
//   });

//   const handleAxisColumn = (e) => {
//     setAxisColumn(e.target.value);
//   };

//   return (
//     <Box className="axisDropdown">
//       {/* Axis Column Selection */}
//       <select id={`${axisType}-axisType`} onChange={handleAxisColumn} value={axisColumn} style={{ marginTop: '3%', width: '100%' }}>
//         <option value="">Select a column</option>
//         {Object.keys(columnTypes).map((colNames) => (
//           <option key={colNames} value={colNames}>
//             {colNames}
//           </option>
//         ))}
//       </select>

//       {/* Scale Type Selection */}
//       {axisColumn && columnTypes[axisColumn] && (
//         <Box id="scaleTypeParent">
//           <Typography style={{ marginRight: "10px", fontSize: '12px', fontFamily: 'Headland One", serif' }}>Scale Type</Typography>
//           {/* <select id="scaleType"> */}
//           <select id={`${axisType}-scaleType`}>
//             {SetScaleType(columnTypes[axisColumn]).map((option) => (
//               <option key={option} value={option}>
//                 {option}
//               </option>
//             ))}
//           </select>
//         </Box>
//       )}
//     </Box>
//   );
// };

// const SetScaleTypeForX = (type) => {
//   switch (type) {
//     case "numeric":
//       return ["Number"];
//     case "datetime":
//       return ["Datetime"];
//     case "string":
//       return ["String"];
//     case "boolean":
//       return ["boolean"];
//     default:
//       return ["Default"];
//   }
// };

// const SetAggregateTypeForY = (type) => {
//   switch (type) {
//     case "numeric":
//       return ["Number", "String"];
//     case "datetime":
//       return ["Datetime", "String"];
//     case "string":
//       return ["String", "Datetime", "Number"];
//     default:
//       return ["Default"];
//   }
// };
