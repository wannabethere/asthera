import React from "react";
import ReactMarkdown from "react-markdown";
import { PersonX, ArrowRepeat, BatteryCharging, GraphUp } from "react-bootstrap-icons"; 

// Dummy raw markdown data
const markdownData = `
### Churn Prediction
Identify at-risk customers based on behavioral patterns, transaction history, and engagement signals.

### LTV Modeling
Identify high-value customers using cohort analysis, historical purchasing behavior, & lifetime engagement trends.

### Lead Scoring
Prioritize leads with the highest likelihood to convert, using real-time behavioral tracking and firmographic data.

### Demand Forecasting
Predict future inventory needs using historical sales, external market trends, and seasonal adjustments.
`;

const icons = [
  <PersonX size={32} className="text-primary mb-3" />,
  <ArrowRepeat size={32} className="text-primary mb-3" />,
  <BatteryCharging size={32} className="text-primary mb-3" />,
  <GraphUp size={32} className="text-primary mb-3" />,
];

export default function ServiceCards() {
  const sections = markdownData.split(/(?=^### )/m).filter(Boolean);

  return (
    <div className="container py-5  text-light">
      <div className="row g-4">
        {sections.map((section, idx) => {
            if(idx !== 0){
                   const titleMatch = section.match(/^### (.*)/);
          const title = titleMatch ? titleMatch[1] : "Untitled";
          const body = section.replace(/^### .*\n/, "").trim();

          return (
            <div className="col-md-6 col-lg-3" key={idx}>
              <div className="card h-100 bg-dark text-light shadow-lg rounded-4">
                <div className="card-body d-flex flex-column justify-content-between">
                  <div>
                    {icons[idx] || icons[0]}
                    <h5 className="card-title fw-bold mb-3">{title}</h5>

                    <ReactMarkdown
                      children={body}
                      components={{
                        p: ({ node, ...props }) => (
                          <p {...props} className="card-text small" />
                        ),
                        strong: ({ node, ...props }) => (
                          <strong {...props} className="fw-semibold text-white" />
                        ),
                        ul: ({ node, ...props }) => (
                          <ul {...props} className="small ps-3" />
                        ),
                        li: ({ node, ...props }) => <li {...props} className="mb-1" />,
                      }}
                    />
                  </div>

                  <button className="btn btn-primary mt-4">Learn More</button>
                </div>
              </div>
            </div>
          );
            }
         
        })}
      </div> 
    </div>
  );
}
