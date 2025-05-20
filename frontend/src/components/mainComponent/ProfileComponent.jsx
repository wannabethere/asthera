import React, { useEffect, useState } from "react";
import {
  Avatar,
  Box,
  Button,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Select,
  Stack,
  Tab,
  Typography,
} from "@mui/material";
import { useTheme } from "../../context/ThemeContext";
import LogoutIcon from "@mui/icons-material/Logout";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import TabList from "@mui/lab/TabList";
import TabContext from "@mui/lab/TabContext";
import TabPanel from "@mui/lab/TabPanel";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";

const ProfileComponent = () => {
  // Profile DorpDown Section
  const [menuAnchor, setMenuAnchor] = useState(null);
  const menuOpen = Boolean(menuAnchor);

  const handleOpen = (event) => {
    setMenuAnchor(event.currentTarget);
  };
  const handleCloseBtn = () => {
    setMenuAnchor(null);
  };

  const handleSettings = () => {
    handleCloseBtn();
    setSettingsOpen(true);
  };
  const handleUpgrade = () => {
    handleCloseBtn();
  };
  const handleLogout = () => {
    handleCloseBtn();
  };

  // open the settings popup
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleSettingsClose = () => setSettingsOpen(false);
  const [tabValue, setTabValue] = useState("general");
  const [language, setLanguage] = useState("en");
  const [theme, setTheme] = useState("light");

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  // Theme Change
  const { rawTheme, handleThemeChange } = useTheme();

  const themes = [
    { label: "Light", value: "light" },
    { label: "Dark", value: "dark" },
    { label: "System", value: "system" },
  ];
  const currentUser = JSON.parse(localStorage.getItem("currentUser"));
  // Name Global Variable
  useEffect(() => {
    // Declare a global variable on the window object
    window.myGlobalVariable = currentUser.name[0].toUpperCase();
  }, []);
  return (
    <>
      <Stack direction="row" spacing={2} alignItems="center">
        <IconButton onClick={handleOpen} size="small" sx={{ ml: 2 }}>
          <Avatar>{window.myGlobalVariable}</Avatar>
        </IconButton>

        <Menu
          anchorEl={menuAnchor}
          open={menuOpen}
          onClose={handleCloseBtn}
          transformOrigin={{ horizontal: "right", vertical: "top" }}
          anchorOrigin={{ horizontal: "right", vertical: "bottom" }}
          PaperProps={{
            elevation: 4,
            sx: {
              mt: 1.5,
              minWidth: 260,
              boxShadow: "0px 6px 20px rgba(0, 0, 0, 0.15)",
              borderRadius: "10px",
              border: "1px solid rgba(43, 43, 43, 0.1)",
              overflow: "visible",
              transition: "background-color 0.3s ease",
            },
          }}
        >
          <MenuItem onClick={handleUpgrade} sx={{ py: 1.2, px: 2.5 }}>
            <ListItemIcon>
              <TrendingUpIcon fontSize="small" />
            </ListItemIcon>
            Upgrade Plan
          </MenuItem>
          <MenuItem onClick={handleSettings} sx={{ py: 1.2, px: 2.5 }}>
            <ListItemIcon>
              <SettingsOutlinedIcon fontSize="small" />
            </ListItemIcon>
            Settings
          </MenuItem>
          <Divider />
          <MenuItem onClick={handleLogout} sx={{ py: 1.2, px: 2.5 }}>
            <ListItemIcon>
              <LogoutIcon fontSize="small" />
            </ListItemIcon>
            Logout
          </MenuItem>
        </Menu>
      </Stack>

      {/* Settings  */}
      <Dialog
        open={settingsOpen}
        onClose={handleSettingsClose}
        maxWidth="sm"
        fullWidth
        sx={{
          "& .MuiPaper-root": {
            borderRadius: "10px",
          },
        }}
      >
        <DialogTitle sx={{ p: 3, pt: 2, pb: 1, fontFamily: "monospace" }}>
          Settings
        </DialogTitle>
        <DialogContent>
          <TabContext value={tabValue}>
            <TabList
              onChange={handleTabChange}
              aria-label="settings tabs"
              className="tabSection"
              centered
              sx={{
                pt: 0,
                "& .MuiTabs-scroller ": {
                  display: "flex",
                  justifyContent: "center",
                },
                "& .MuiTabs-flexContainer": {
                  justifyContent: "center",
                },
                "& .MuiTabs-list": {
                  width: "190px",
                  background: "rgb(237 236 236 / 74%)",
                  borderRadius: "14px",
                },
                "& .MuiTab-root": {
                  minHeight: "auto",
                  padding: "8px",
                  lineHeight: 1,
                },
                "& .MuiTabs-indicator": {
                  display: "none",
                },
                "& .Mui-selected": {
                  backgroundColor: "white",
                  color: "black !important",
                  m: "5px",
                  ml: 0,
                  mr: 0,
                  p: "10px",
                  borderRadius: "10px",
                },
                "& .MuiButtonBase-root": {
                  fontFamily: "monospace",
                },
              }}
            >
              <Tab label="General" value="general" />
              <Tab label="About" value="about" />
            </TabList>

            <TabPanel value="general" sx={{ pt: 2 }}>
              <Box
                sx={{
                  mb: 1,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <Typography
                  variant="subtitle1"
                  gutterBottom
                  className="settingsPopupFont"
                >
                  Language
                </Typography>
                <FormControl variant="outlined">
                  <Select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    sx={{
                      "& .MuiOutlinedInput-notchedOutline": {
                        border: "none",
                      },
                      "&. MuiOutlinedInput-root": {
                        background: "rgb(237 236 236 / 74%)",
                        padding: 0,
                        width: "113px",
                      },
                      "& .MuiSelect-select": {
                        pt: "5px",
                        pb: "5px",
                      },
                    }}
                  >
                    <MenuItem value="en">English</MenuItem>
                    <MenuItem value="es">Spanish</MenuItem>
                    <MenuItem value="fr">French</MenuItem>
                    <MenuItem value="de">German</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              <Divider />
              <Box
                sx={{
                  mt: 1,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <Typography
                  variant="subtitle1"
                  gutterBottom
                  className="settingsPopupFont"
                >
                  Theme
                </Typography>
                <FormControl variant="outlined">
                  <Select
                    label="Theme"
                    value={rawTheme}
                    onChange={(e) => handleThemeChange(e.target.value)}
                    renderValue={(selected) => {
                      const selectedTheme = themes.find(
                        (t) => t.value === selected
                      );
                      return selectedTheme?.label;
                    }}
                    sx={{
                      "& .MuiOutlinedInput-notchedOutline": {
                        border: "none",
                      },
                      "&. MuiOutlinedInput-root": {
                        background: "rgb(237 236 236 / 74%)",
                        padding: 0,
                        width: "113px",
                      },
                      "& .MuiSelect-select": {
                        pt: "5px",
                        pb: "5px",
                      },
                    }}
                    MenuProps={{
                      PaperProps: {
                        sx: {
                          width: "14%",
                        },
                      },
                    }}
                  >
                    {themes.map((theme) => (
                      <MenuItem key={theme.value} value={theme.value}>
                        <ListItemText primary={theme.label} />
                        {rawTheme === theme.value && (
                          <Box ml="auto">
                            <CheckCircleIcon
                              fontSize="small"
                              sx={{ display: "flex", justifyContent: "center" }}
                            />
                          </Box>
                        )}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>
            </TabPanel>

            <TabPanel value="about" sx={{ pt: 2 }}>
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  mb: 2,
                  "& .MuiTypography-root": { fontFamily: "monospace" },
                }}
              >
                <Typography variant="subtitle1">Terms of Use</Typography>
                <Button
                  variant="outlined"
                  sx={{
                    border: "1px solid",
                    borderColor: (theme) =>
                      theme.palette.mode === "dark" ? "#555" : "#e0e0e0",
                    borderRadius: "8px",
                    color: (theme) =>
                      theme.palette.mode === "dark" ? "#e0e0e0" : "#333",
                    fontFamily: "monospace",
                  }}
                >
                  View
                </Button>
              </Box>
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  "& .MuiTypography-root": { fontFamily: "monospace" },
                }}
              >
                <Typography variant="subtitle1">Privacy Policy</Typography>
                <Button
                  variant="outlined"
                  sx={{
                    border: "1px solid",
                    borderColor: (theme) =>
                      theme.palette.mode === "dark" ? "#555" : "#e0e0e0",
                    borderRadius: "8px",
                    color: (theme) =>
                      theme.palette.mode === "dark" ? "#e0e0e0" : "#333",
                    fontFamily: "monospace",
                  }}
                >
                  View
                </Button>
              </Box>
            </TabPanel>
          </TabContext>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default ProfileComponent;
