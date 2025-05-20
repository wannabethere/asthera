import {
  Box,
  Button,
  FormControl,
  FormHelperText,
  Stack,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import SimpleReactValidator from "simple-react-validator";
import { InputBox, PasswordInputBox } from "../Common";

export default function SignUp() {
  const [fname, setFname] = useState("");
  const [lname, setLname] = useState("");
  const [emailSignUp, setEmailSignUp] = useState("");
  const [passwordSignUp, setPasswordSignUp] = useState("");
  const [hideAndShowPaswordMain, setHideAndShowPaswordMain] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [hideAndShowPaswordConfirm, setHideAndShowPaswordConfirm] =
    useState("");
  const [errorForPwdNotMatched, setErrorForPwdNotMatched] = useState(false);
  const [showError, setShowError] = useState("");
  const [isSubmitted, setIsSubmitted] = useState(false);

  const [validator] = useState(new SimpleReactValidator());
  const navigate = useNavigate();

  useEffect(() => {
    if (isSubmitted) {
      validator.purgeFields();
      setIsSubmitted(false);
    }
  }, [isSubmitted, validator]);

  const handlePassword = () => {
    setHideAndShowPaswordMain(
      (hideAndShowPaswordMain) => !hideAndShowPaswordMain
    );
  };

  const handleConfirmPassword = () => {
    setHideAndShowPaswordConfirm(
      (hideAndShowPaswordConfirm) => !hideAndShowPaswordConfirm
    );
  };

  const handleSignUpSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitted(true);
    setErrorForPwdNotMatched(false);
    setShowError("");

    if (validator.allValid()) {
      if (passwordSignUp !== confirmPassword && confirmPassword !== "") {
        setErrorForPwdNotMatched(true);
        setShowError("Passwords do not match");
        return;
      }

      try {
        const response = await fetch("http://127.0.0.1:8000/signup", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email: emailSignUp,
            password: passwordSignUp,
            name: `${fname} ${lname}`,
          }),
        });

        const data = await response.json();

        if (!response.ok) {
          setShowError(data.detail || "Signup failed");
          return;
        }

        localStorage.setItem("currentUser", JSON.stringify(data));

        navigate("/signupSucess");
      } catch (error) {
        console.error("Signup error:", error);
        setShowError("Something went wrong. Please try again.");
      }
    } else {
      validator.showMessages();
    }
  };

  return (
    <>
      <Box className="signUpBox">
        <Stack className="Stack" spacing={{ xs: 1, sm: 2 }}>
          <Box>
            <h2 style={{ textAlign: "center", color: "white" }}>
              Create your Account
            </h2>
          </Box>

          <FormControl>
            <InputBox
              name="fname"
              placeholder="First name"
              id="my-fname"
              value={fname}
              onChange={(e) => setFname(e.target.value)}
            />

            <FormHelperText style={{ color: `red`, marginLeft: "24px" }}>
              {validator.message("firstname", fname, "required")}
            </FormHelperText>
          </FormControl>

          <FormControl>
            <InputBox
              name="lName"
              placeholder="Last Name"
              id="my-lname"
              value={lname}
              onChange={(e) => setLname(e.target.value)}
            />
            <FormHelperText style={{ color: `red`, marginLeft: "24px" }}>
              {validator.message("lastname", lname, "required")}
            </FormHelperText>
          </FormControl>

          <FormControl>
            <InputBox
              name="emailSignUp"
              placeholder="Email address"
              id="my-emailSignUp"
              value={emailSignUp}
              type="email"
              onChange={(e) => setEmailSignUp(e.target.value)}
            />
            <FormHelperText style={{ color: `red`, marginLeft: "24px" }}>
              {validator.message("email", emailSignUp, "required|email")}
            </FormHelperText>
          </FormControl>

          <FormControl>
            <PasswordInputBox
              name="passwordSignUp"
              placeholder="Password"
              id="my-passwordSignUp"
              value={passwordSignUp}
              type={hideAndShowPaswordMain}
              onChange={(e) => setPasswordSignUp(e.target.value)}
              handlePassword={handlePassword}
            />
            <FormHelperText style={{ color: `red`, marginLeft: "24px" }}>
              {validator.message("password", passwordSignUp, "required|min:8")}
            </FormHelperText>
          </FormControl>

          <FormControl>
            <PasswordInputBox
              name="confirmPassword"
              placeholder="Confirm password"
              id="my-confirmPassword"
              value={confirmPassword}
              type={hideAndShowPaswordConfirm}
              onChange={(e) => setConfirmPassword(e.target.value)}
              handleConfirmPassword={handleConfirmPassword}
            />
            <FormHelperText style={{ color: `red`, marginLeft: "24px" }}>
              {validator.message(
                "confirmPassword",
                confirmPassword,
                "required|min:8"
              )}
            </FormHelperText>
            {/* {validator.message('confirmPassword', confirmPassword, 'required|min:6') && (
                        <FormHelperText sx={{ ml: 3 }} error>{validator.message('confirmPassword', confirmPassword, 'required|min:6')}</FormHelperText>
                    )} */}

            {errorForPwdNotMatched && (
              <FormHelperText style={{ color: `red`, marginLeft: "24px" }}>
                {showError}
              </FormHelperText>
            )}
          </FormControl>

          <Button id="loginButton" type="submit" onClick={handleSignUpSubmit}>
            Sign Up
          </Button>

          <Box sx={{ padding: 0, textAlign: "start", display: "flex", ml: 3 }}>
            <Typography style={{ color: "white", marginLeft: "5%" }}>
              Already have an account ?
            </Typography>
            <Link to="/" style={{ textDecoration: "none", marginLeft: "5px" }}>
              <Typography style={{ color: "white" }}>Log in</Typography>
            </Link>
          </Box>
        </Stack>
      </Box>
    </>
  );
}

/* padding: '4% 0%' */
// Primary Color: Dark Gray (#1D1D1D) or Black (#212121)
// Accent Color: Neon Purple (#8E44AD) or Electric Green (#39FF14)
// Text Color: White (#FFFFFF) or Light Gray (#BDC3C7)
// Background: Deep Space Blue (#1F2A44) or Dark Navy (#2C3E50)
// Button/Highlight Color: Bright Cyan (#00E5FF)
