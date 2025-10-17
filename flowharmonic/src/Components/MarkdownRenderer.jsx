 

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

// Extract plain text from Markdown children
const extractText = (children) => {
  if (!children) return "";
  if (typeof children === "string") return children;
  if (Array.isArray(children)) return children.map(extractText).join("");
  if (typeof children === "object" && children.props)
    return extractText(children.props.children);
  return "";
};

// Generate slug IDs
const slugify = (text) =>
  text
    .toLowerCase()
    .replace(/[^\w]+/g, "-") // replace spaces & symbols with hyphen
    .replace(/^-+|-+$/g, ""); // trim

const MarkdownRenderer = ({ content }) => {
  // Build TOC once per content change
  const toc = useMemo(() => {
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = content;

    const headings = [];
    const regex = /^##\s+(.*)$/gm; // only H2 headings from Markdown
    let match;
    while ((match = regex.exec(content)) !== null) {
      const text = match[1].trim();
      const id = slugify(text);
      headings.push({ id, text });
    }
    return headings;
  }, [content]);

  const [activeId, setActiveId] = React.useState("");

const handleClick = (id) => {
  setActiveId(id);
  const el = document.getElementById(id);
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
};

  return (
    <div className="container-fluid py-4 bg-light">
      <div className="row">
        {/* Sidebar TOC */}
        {/* <aside className="col-md-3 mb-4">
          {toc.length > 0 && (
            <div
              className="bg-white shadow-sm rounded-3 p-3 sticky-top"
              style={{ top: "80px" }}
            >
               <h6 className="text-uppercase text-muted small mb-3">Table of Contents</h6>
              <ul className="list-unstyled small">
                {toc.map((item) => (
                  <li key={item.id} className="mb-1">
                    <a
                      href={`#${item.id}`}
                      className="text-decoration-none text-secondary"
                    >
                      {item.text}
                    </a>
                  </li>
                ))}
              </ul>
              <ul className="list-unstyled small">
                {toc.map((item) => (
                  <li key={item.id} className="mb-1">
                    <button
                      type="button"
                      className="btn btn-link p-0 text-decoration-none text-secondary"
                      onClick={() => {
                        const el = document.getElementById(item.id);
                        if (el) {
                          el.scrollIntoView({
                            behavior: "smooth",
                            block: "start",
                          });
                        }
                      }}
                    >
                      {item.text}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside> */}
        <aside className="col-lg-3 mb-4">
          {toc.length > 0 && (
            <div
              className="sidebar p-3 rounded-4 shadow-sm bg-white sticky-top"
              style={{ top: "80px" }}
            >
              <h6 className="text-uppercase text-muted fw-bold mb-3">
                Table of Contents
              </h6>
              <nav className="nav flex-column">
                {toc.map((item) => (
                  // <button
                  //   key={item.id}
                  //   type="button"
                  //   className={`toc-item text-start btn btn-link p-0 nav-link ${
                  //     item.level === 1
                  //       ? "level-1 fw-semibold"
                  //       : item.level === 2
                  //       ? "level-2 ms-3"
                  //       : "level-3 ms-4 text-muted small"
                  //   }`}
                  //   onClick={() => {
                  //     const el = document.getElementById(item.id);
                  //     if (el) {
                  //       el.scrollIntoView({
                  //         behavior: "smooth",
                  //         block: "start",
                  //       });
                  //     }
                  //   }}
                  // >
                  //   {item.text}
                  // </button>
                  <button
                    key={item.id}
                    type="button"
                    className={`toc-item text-start btn btn-link nav-link ${
                      activeId === item.id ? "active" : ""
                    } ${
                      item.level === 1
                        ? "level-1 fw-semibold"
                        : item.level === 2
                        ? "level-2 ms-3"
                        : "level-3 ms-4 text-muted small"
                    }`}
                    onClick={() => handleClick(item.id)}
                  >
                    {item.text}
                  </button>
                ))}
              </nav>
            </div>
          )}
        </aside>

        {/* Main Content */}
        <main className="col-md-9">
          <div className="bg-white rounded-4 shadow-sm p-4 px-5">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
              components={{
                h1: ({ node, ...props }) => (
                  <h1 className="fw-bold mt-4 mb-3" {...props} /> // no id for H1
                ),
                h2: ({ node, ...props }) => {
                  const text = extractText(props.children);
                  const id = slugify(text);
                  return (
                    <h2 id={id} className="fw-semibold mt-4 mb-3" {...props}>
                      {props.children}
                    </h2>
                  );
                },
                h3: ({ node, ...props }) => (
                  <h3 className="fw-semibold mt-4 mb-2" {...props} />
                ), // no id
                p: ({ node, ...props }) => (
                  <p className="text-secondary lh-lg" {...props} />
                ),
                a: ({ node, ...props }) => (
                  <a className="text-primary text-decoration-none" {...props} />
                ),
                ul: ({ node, ...props }) => <ul className="ms-4" {...props} />,
                li: ({ node, ...props }) => <li className="mb-1" {...props} />,
                code: ({ node, inline, ...props }) =>
                  inline ? (
                    <code className="bg-light px-1 rounded" {...props} />
                  ) : (
                    <pre
                      className="bg-dark text-white p-3 rounded-3 overflow-auto"
                      {...props}
                    />
                  ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        </main>
      </div>
    </div>
  );
};

export default MarkdownRenderer;
