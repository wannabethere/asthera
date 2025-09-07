 



import React, { useEffect } from "react";
import { useLocation } from "react-router-dom";
import DocumentationLayout from "../Components/DocumentationLayout.jsx";

const MarkdownPage = () => {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const location = useLocation();
  const content = location.state?.content || "# No content provided";

  return <DocumentationLayout content={content} />;
};

export default MarkdownPage;
