// import React, { useEffect, useState } from "react";
// import { loadMarkdown } from "../utils/loadMarkdown";

// const ProblemsSection = () => {
//   const [data, setData] = useState(null);

//   useEffect(() => {
//     loadMarkdown("/content/home/problems.md").then(setData);
//   }, []);

//   if (!data) return null;

//   return (
//     <section className="problems py-5 px-3 bg-dark text-white">
//       <h2 className="h2 fw-bold text-center mb-5">
//         {data.frontmatter.title}
//       </h2>
//       <div className="row row-cols-1 row-cols-md-3 g-4">
//         {data.frontmatter.items.map((item, idx) => (
//           <div key={idx} className="col">
//             <div className="problem-card border p-4 rounded-3 bg-secondary">
//               <h3 className="h4 fw-semibold">{item.heading}</h3>
//               <p className="mt-3 text-muted">{item.text}</p>
//             </div>
//           </div>
//         ))}
//       </div>
//     </section>
//   );
// };

// // export default ProblemsSection;
// import React, { useEffect, useState } from "react";
// import { loadMarkdown } from "../utils/loadMarkdown";
// import "../style/problems.css"; // make sure path matches your project

// const VariantCard = ({ item, tall = false }) => {
//   const variant = (item.variant || "default").toLowerCase();
//   return (
//     <article
//       className={`problem-card ${tall ? "tall-card" : ""} accent-${variant}`}
//       aria-labelledby={`h-${item.heading.replace(/\s+/g, "-").toLowerCase()}`}
//     >
//       <h3 id={`h-${item.heading.replace(/\s+/g, "-").toLowerCase()}`} className="card-heading">
//         {item.heading}
//       </h3>
//       <div className="card-text">
//         {item.text &&
//           item.text.split("\n\n").map((para, i) => (
//             <p key={i} className="mb-2 text-muted small">
//               {para}
//             </p>
//           ))}
//       </div>
//     </article>
//   );
// };

// const ProblemsSection = () => {
//   const [data, setData] = useState(null);

//   useEffect(() => {
//     loadMarkdown("/content/home/problems.md").then(setData);
//   }, []);

//   if (!data) return null;

//   const items = data.frontmatter?.items || [];

//   // If we have 5 or more items, render the three-column "image-like" layout:
//   if (items.length >= 5) {
//     return (
//       <section className="problems-section py-5 px-3">
//         <div className="container">
//           <h2 className="section-title text-center fw-bold mb-5">{data.frontmatter.title}</h2>

//           <div className="row gx-4 gy-4 align-items-start">
//             {/* LEFT: large tall card */}
//             <div className="col-lg-4 d-flex flex-column">
//               <VariantCard item={items[0]} tall />
//             </div>

//             {/* MIDDLE: two stacked */}
//             <div className="col-lg-4 d-flex flex-column gap-4">
//               <VariantCard item={items[1]} />
//               <VariantCard item={items[2]} />
//             </div>

//             {/* RIGHT: two stacked */}
//             <div className="col-lg-4 d-flex flex-column gap-4">
//               <VariantCard item={items[3]} />
//               <VariantCard item={items[4]} />
//             </div>
//           </div>
//         </div>
//       </section>
//     );
//   }

//   // Fallback: simple responsive grid like your original implementation
//   return (
//     <section className="problems-section py-5 px-3">
//       <div className="container">
//         <h2 className="section-title text-center fw-bold mb-5">{data.frontmatter.title}</h2>

//         <div className="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4">
//           {items.map((item, idx) => (
//             <div key={idx} className="col">
//               <VariantCard item={item} />
//             </div>
//           ))}
//         </div>
//       </div>
//     </section>
//   );
// };

// export default ProblemsSection;


import React, { useEffect, useState } from "react";
import { loadMarkdown } from "../utils/loadMarkdown";
import "../style/problems.css";

const VariantCard = ({ item, tall = false, sizeClass = "", leftTitle }) => {
  // leftTitle: if provided, render the big section title inside this card
  const slug = item?.heading?.replace(/\s+/g, "-").toLowerCase() || "card";
  return (
    <article
      className={`problem-card ${tall ? "tall-card" : ""} ${sizeClass} accent-${(item.variant || "default").toLowerCase()}`}
      aria-labelledby={`h-${slug}`}
    >
   

      {/* card internal heading (this is now inside the card as requested) */}
      <h3 id={`h-${slug}`} className="card-heading">
        {item.heading}
      </h3>

      <div className="card-text">
        {item.text &&
          item.text.split("\n\n").map((para, i) => (
            <p key={i} className="mb-2   small text-white">
              {para}
            </p>
          ))}
      </div>
    </article>
  );
};

const ProblemsSection = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    loadMarkdown("/content/home/problems.md").then(setData);
  }, []);

  if (!data) return null;

  const items = data.frontmatter?.items || [];

  // 5+ items -> render the asymmetric 3-column layout (mimics provided image)
  if (items.length >= 5) {
    return (
      <section className="problems-section py-5 px-3">
        <div className="container">
          {/* NOTE: title now appears inside the left card; we do not render the title above */}
          <div className="row gx-4 gy-4 align-items-start">
            {/* LEFT: large tall card (index 0) */}
            <div className="col-lg-4 d-flex flex-column">
              {data.frontmatter.title  && (
                <div className="left-big-title" aria-hidden="true">
                  {data.frontmatter.title}
                </div>
              )}
              <VariantCard
                item={items[0]}
                tall
                sizeClass="card-size-0"
                leftTitle={data.frontmatter.title}
              />
            </div>

            {/* MIDDLE: two stacked (indexes 1 & 2) */}
            <div className="col-lg-4 d-flex flex-column gap-4 mt-5">
              <VariantCard item={items[1]} sizeClass="card-size-1" />
              <VariantCard item={items[2]} sizeClass="card-size-2" />
            </div>

            {/* RIGHT: two stacked (indexes 3 & 4) */}
            <div className="col-lg-4 d-flex flex-column gap-4">
              <VariantCard item={items[3]} sizeClass="card-size-3" />
              <VariantCard item={items[4]} sizeClass="card-size-4" />
            </div>
          </div>
        </div>
      </section>
    );
  }

  // Fallback: simple responsive grid (title above grid)
  return (
    <section className="problems-section py-5 px-3">
      <div className="container">
        <h2 className="section-title text-center fw-bold mb-5">{data.frontmatter.title}</h2>

        <div className="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4">
          {items.map((item, idx) => (
            <div key={idx} className="col">
              <VariantCard item={item} />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ProblemsSection;
