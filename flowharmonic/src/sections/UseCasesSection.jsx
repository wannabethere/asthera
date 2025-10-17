// import React, { useEffect, useState } from "react";
// import { loadMarkdown } from "../utils/loadMarkdown";

// const UseCasesSection = () => {
//   const [data, setData] = useState(null);

//   useEffect(() => {
//     loadMarkdown("/content/home/usecases.md").then(setData);
//   }, []);

//   if (!data) return null;

//   return (
//     <section className="usecases py-5 px-3 bg-light">
//       <h2 className="h2 fw-bold text-center mb-5">
//         {data.frontmatter.title}
//       </h2>
//       <div className="row row-cols-1 row-cols-md-2 row-cols-lg-4 g-4">
//         {data.frontmatter.cases.map((uc, idx) => (
//           <div key={idx} className="col">
//             <div className="usecase-card p-4 border rounded-3 shadow-sm bg-white">
//               <h3 className="h5 fw-semibold">{uc.heading}</h3>
//               <p className="mt-3 text-muted">{uc.text}</p>
//             </div>
//           </div>
//         ))}
//       </div>
//     </section>
//   );
// };

// export default UseCasesSection;
import React, { useEffect, useState } from "react";
import { loadMarkdown } from "../utils/loadMarkdown";
import "../style/usecases.css";

const formatDate = (raw) => {
  try {
    const d = new Date(raw);
    if (isNaN(d)) return raw;
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return raw;
  }
};

const UseCasesSection = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    loadMarkdown("/content/home/usecases.md").then(setData);
  }, []);

  if (!data) return null;

  const cases = data.frontmatter?.cases || [];

  return (
    <section className="usecases py-5 px-3">
      <div className="container-fluid container-padding">
        <h2 className="  display-3  text-start fw-bold mb-5">{data.frontmatter.title}</h2>

        <div className="row row-cols-1 row-cols-md-2 row-cols-lg-4 g-4">
          {cases.map((uc, idx) => (
            <div key={idx} className="col">
              <article className="usecase-card border rounded-3 shadow-sm bg-white h-100 d-flex flex-column">
                <div className="thumb-wrapper">
                  <img
                    src={uc.image || "/useCase/default.webp"}
                    alt={uc.heading}
                    className="thumb img-fluid"
                    loading="lazy"
                  />
                </div>

                <div className="card-inner p-3 d-flex flex-column flex-grow-1">
                  <h3 className="h5 fw-semibold mb-1">{uc.heading}</h3>

                  <div className="publish small text-muted mb-2">{formatDate(uc.publish)}</div>

                  <p className="mt-2 text-muted mb-3">{uc.text}</p>

                  {/* flexible spacer to push possible CTA to bottom */}
                  <div className="mt-auto"></div>
                </div>
              </article>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default UseCasesSection;
