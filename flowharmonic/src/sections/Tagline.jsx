// import React, { useEffect, useState } from "react";
// import { loadMarkdown } from "../utils/loadMarkdown";

// const Tagline = () => {
//   const [data, setData] = useState(null);

//   useEffect(() => {
//     loadMarkdown("/content/home/tagline.md").then(setData);
//   }, []);

//   if (!data) return null;

//   return (
//     <section className="tagline py-5 px-3 text-center">
//       <h2 className="h2 fw-bold">{data.frontmatter.headline}</h2>
//       <p className="mt-3 fs-5 text-secondary">
//         {data.frontmatter.description}
//       </p>
//     </section>
//   );
// };

// export default Tagline;
import React, { useEffect, useState } from "react";
import { loadMarkdown } from "../utils/loadMarkdown";
import '@fortawesome/fontawesome-free/css/all.min.css';
import { Link } from "react-router-dom";

const Tagline = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    loadMarkdown("/content/home/tagline.md").then(setData);
  }, []);

  if (!data) return null;

  const { headline, description, cards, button } = data.frontmatter;

  return (
    <section className="tagline    tagline-container-padding">
      {/* Headline & Description */}
      <h2 className="display-3  ps-4  col-md-7  fw-bold">{headline}</h2>
      <div className="col-md-12 d-flex justify-content-end">
        <p className="mt-3 fs-5 text-secondary col-md-8 p-3 text-dark">
          {description}
        </p>
      </div>

      <hr className="" />

      {/* Cards */}
      <div className="container-fluid py-5">
        <div className="row">
          {cards?.map((card, index) => (
            <div className="col-md-6 mb-4" key={index}>
              <div className="card h-100 p-4 shadow-sm border-0 ">
                {card.icon && <i className={`${card.icon} fa-2x mb-3`}></i>}
                <h5 className="fw-bold text-start">{card.title}</h5>
                <p className="text-muted text-start">{card.text}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="col-md-12 d-flex justify-content-end pt-5"
        style={{
            borderBottom: "4px solid #96aecfcf"
        }}>
          <Link to={"/about"}>
            <button className="btn fw-bold">{button}</button>
          </Link>
        </div>
      </div>
    </section>
  );
};

export default Tagline;
