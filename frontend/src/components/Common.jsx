import { InputAdornment, OutlinedInput } from "@mui/material";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";

export default function Common() {
  return "";
}

export const InputBox = ({
  name,
  placeholder,
  id,
  value,
  onChange,
  type,
  endAdornment,
}) => {
  return (
    <>
      <OutlinedInput
        className=""
        name={name}
        sx={{
          borderRadius: "10px",
          width: "90%;",
          ml: 3,
          border: "2px solid white",
          color: "white",
        }}
        placeholder={placeholder}
        id={id}
        value={value}
        onChange={onChange}
        type={type}
        endAdornment={endAdornment}
      />
    </>
  );
};

export const PasswordInputBox = ({
  name,
  placeholder,
  id,
  value,
  type,
  onChange,
  handlePassword,
  handleConfirmPassword,
}) => {
  return (
    <>
      <InputBox
        name={name}
        placeholder={placeholder}
        id={id}
        value={value}
        type={type ? "text" : "password"}
        onChange={onChange}
        endAdornment={
          <InputAdornment position="start">
            {name === "confirmPassword" ? (
              type ? (
                <VisibilityOffIcon
                  sx={{ color: "white" }}
                  onClick={handleConfirmPassword}
                />
              ) : (
                <VisibilityIcon
                  sx={{ color: "white" }}
                  onClick={handleConfirmPassword}
                />
              )
            ) : type ? (
              <VisibilityOffIcon
                sx={{ color: "white" }}
                onClick={handlePassword}
              />
            ) : (
              <VisibilityIcon
                sx={{ color: "white" }}
                onClick={handlePassword}
              />
            )}
          </InputAdornment>
        }
      />
    </>
  );
};
