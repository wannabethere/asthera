import React, { useContext } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { AppBar, Toolbar, Box, Typography } from '@mui/material';

const AppTopToolBar = () => {
  const { user, setUser } = useAuth();  // Make sure you're using the auth context
  const navigate = useNavigate();

  // Add null check for user data
  const userEmail = user?.email || 'Guest';
  const userName = user?.first_name ? `${user.first_name} ${user.last_name}` : 'Guest';

  return (
    <AppBar position="static" color="default" elevation={0}>
      <Toolbar>
        {/* ... other toolbar items ... */}
        
        {/* User menu with null checks */}
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Typography variant="body2" sx={{ mr: 2 }}>
            {userName}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {userEmail}
          </Typography>
          {/* ... rest of the user menu ... */}
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default AppTopToolBar; 