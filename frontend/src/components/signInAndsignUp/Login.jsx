import { useState } from 'react';
import { Box, Button, Stack, Typography, TextField, ToggleButton, ToggleButtonGroup } from "@mui/material";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from '../../contexts/AuthContext';
import { useOktaAuth } from '@okta/okta-react';
import "./../../css/LoginAndSignUp.css";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginType, setLoginType] = useState("default");
  const { oktaAuth } = useOktaAuth();
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLoginTypeChange = (event, newLoginType) => {
    if (newLoginType !== null) {
      setLoginType(newLoginType);
    }
  };

  const handleOktaLogin = async () => {
    await oktaAuth.signInWithRedirect();
  };

  const handleSuperUserLogin = async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ 
          email: "admin@example.com", 
          password: "admin123" 
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        alert(data.detail || "Superuser login failed");
        return;
      }
      localStorage.setItem("currentUser", JSON.stringify(data));
      navigate("/navbar");
    } catch (error) {
      console.error("Error during superuser login:", error);
      alert("Something went wrong during superuser login.");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch("http://127.0.0.1:8000/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email: username, password: password }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to login');
      }

      // Store the token in localStorage
      localStorage.setItem('token', data.access_token);

      // Fetch user data
      const userResponse = await fetch('http://localhost:8000/auth/me', {
        headers: {
          'Authorization': `Bearer ${data.access_token}`,
        },
      });

      if (!userResponse.ok) {
        throw new Error('Failed to fetch user data');
      }

      const userData = await userResponse.json();
      
      // Store user data in localStorage
      localStorage.setItem('currentUser', JSON.stringify({
        id: userData.id,
        email: userData.email,
        first_name: userData.first_name,
        last_name: userData.last_name,
      }));

      // Call the login function from AuthContext
      login(data.access_token, {
        id: userData.id,
        email: userData.email,
        first_name: userData.first_name,
        last_name: userData.last_name,
      });
     
      navigate("/navbar");
    } catch (error) {
      console.error("Error during login:", error);
      alert("Something went wrong during login.");
    }
  };

  return (
    <>
      <Box className="LoginformBox">
        <Stack className="Stack" spacing={{ xs: 1, sm: 2 }}>
          <Box>
            <h2 style={{ textAlign: "center", color: "white" }}>Login</h2>
          </Box>
          <ToggleButtonGroup
            value={loginType}
            exclusive
            onChange={handleLoginTypeChange}
            aria-label="login type"
          >
            <ToggleButton value="default" aria-label="default login">
              Default Login
            </ToggleButton>
            <ToggleButton value="okta" aria-label="okta login">
              Okta Login
            </ToggleButton>
          </ToggleButtonGroup>
          {loginType === "default" ? (
            <>
              <TextField
                label="Email"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                fullWidth
                margin="normal"
              />
              <TextField
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                fullWidth
                margin="normal"
              />
              <Button id="loginButton" onClick={handleSubmit}>
                Login with Email/Password
              </Button>
              <Button 
                id="superUserButton" 
                onClick={handleSuperUserLogin}
                style={{ 
                  backgroundColor: '#8E44AD',
                  color: 'white',
                  marginTop: '10px'
                }}
              >
                Login as Superuser
              </Button>
            </>
          ) : (
            <Button id="loginButton" onClick={handleOktaLogin}>
              Login with Okta
            </Button>
          )}
          <Box sx={{ padding: 0, textAlign: "start", display: "flex", ml: 3 }}>
            <Typography style={{ color: "white", marginLeft: "5%" }}>
              Don't have an Account ?
            </Typography>
            <Link
              to="/signup"
              style={{ textDecoration: "none", marginLeft: "5px" }}
            >
              <Typography style={{ color: "white" }}>SignUp</Typography>
            </Link>
          </Box>
        </Stack>
      </Box>
    </>
  );
}

// Primary Color: Dark Gray (#1D1D1D) or Black (#212121)
// Accent Color: Neon Purple (#8E44AD) or Electric Green (#39FF14)
// Text Color: White (#FFFFFF) or Light Gray (#BDC3C7)
// Background: Deep Space Blue (#1F2A44) or Dark Navy (#2C3E50)
// Button/Highlight Color: Bright Cyan (#00E5FF)
