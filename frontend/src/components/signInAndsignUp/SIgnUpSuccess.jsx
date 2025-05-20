import { Box, Button, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";

export const SignUpSuccess = () => {
  const styles = {
    backgroundColor: "white",
    boxShadow: "0px 0px 10px white",
    width: "10%",
    borderRadius: "10px",
    transform: "translateX(20px)",
    color: "black",
    padding: "10px",
    marginTop: "2%",
  };

  const navigate = useNavigate();
  const handleSubmitAfterSignUp = () => {
    navigate("/");
  };

  return (
    <>
      <Box className="SuccessPage">
        <Typography variant="h5">Account Succesfully Created</Typography>
        <Button style={styles} type="submit" onClick={handleSubmitAfterSignUp}>
          Login
        </Button>
      </Box>
    </>
  );
};
