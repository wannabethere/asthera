import "./App.css";
import { Route, Routes, useLocation, BrowserRouter } from "react-router-dom";
import Login from "./components/signInAndsignUp/Login";
import SignUp from "./components/signInAndsignUp/SignUp";
import { useEffect, useMemo } from "react";
import SideNavBar from "./components/mainComponent/SideNavBar";
import { SignUpSuccess } from "./components/signInAndsignUp/SIgnUpSuccess";
import { ConversationProvider } from "./context/ConversationContext";
import { ThreadsProvider } from "./context/ThreadsContext";
import { ReportDashboard } from "./components/navComponents/ReportDashboardComponent";
import {
  ThemeProvider as MuiThemeProvider,
  createTheme,
} from "@mui/material/styles";
import { ThemeChangeProvider, useTheme } from "./context/ThemeContext";
import { CssBaseline } from "@mui/material";
import { Security } from '@okta/okta-react';
import { OktaAuth } from '@okta/okta-auth-js';
import { useNavigate } from "react-router-dom";

const oktaAuth = new OktaAuth({
  issuer: 'https://your-okta-domain.okta.com/oauth2/default',
  clientId: 'your-client-id',
  redirectUri: window.location.origin + '/login/callback',
});

function AppWrapper() {
  const navigate = useNavigate();
  const restoreOriginalUri = async (_oktaAuth, originalUri) => {
    navigate(originalUri || '/');
  };
  return (
    <Security oktaAuth={oktaAuth} restoreOriginalUri={restoreOriginalUri}>
    <ThemeChangeProvider>
      <CssBaseline />
      <ThreadsProvider>
        <ConversationProvider>
          <App />
        </ConversationProvider>
      </ThreadsProvider>
    </ThemeChangeProvider>
    </Security>
  );
}

function App() {
  const { appTheme } = useTheme();
  const location = useLocation();
  // Theme change
  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode: appTheme === "dark" ? "dark" : "light",
          background: {
            default: appTheme === "dark" ? "#292a2e" : "#ffffff",
            paper: appTheme === "dark" ? "#222327" : "#f5f5f5",
          },
        },
        components: {
          MuiCssBaseline: {
            styleOverrides: {
              body: {
                backgroundColor: appTheme === "dark" ? "#121212" : "#ffffff",
              },
            },
          },
        },
      }),
    [appTheme]
  );

  useEffect(() => {
    const loc = location.pathname;
    const pathNames = ["/", "/signup", "/signupSucess"];

    const isTrue = pathNames.includes(loc);
    if (isTrue) {
      document.body.style.background =
        "linear-gradient(110deg,  #d9b878, #6f4f43, #0d2528)";
      document.body.style.backgroundSize = "cover";
      document.body.style.backgroundRepeat = "no-repeat";
      document.body.style.backgroundAttachment = "fixed";
    } else {
      document.body.style.background = "";
    }
  }, [location]);

  return (
    <MuiThemeProvider theme={theme}>
      <div
        className="App"
        style={{
          backgroundColor: theme.palette.background.default,
          minHeight: "100vh",
        }}
      >
        <Routes>
          <Route path="" element={<Login />}></Route>
          <Route path="signup" element={<SignUp />}></Route>
          <Route path="/signupSucess" element={<SignUpSuccess />}></Route>
          <Route path="/navbar" element={<SideNavBar />}></Route>
          <Route path="/report-dashboard" element={<ReportDashboard />}></Route>
          <Route path="/navbar/thread" element={<SideNavBar />} />
        </Routes>
      </div>
    </MuiThemeProvider>
  );
}

export default function AppWithRouter() {
  return (
    <BrowserRouter>
      <AppWrapper />
    </BrowserRouter>
  );
}
