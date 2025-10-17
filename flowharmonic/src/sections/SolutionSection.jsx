import React, { useEffect, useState } from "react";
import { loadMarkdown } from "../utils/loadMarkdown";

import '@fortawesome/fontawesome-free/css/all.min.css';
import { Link } from "react-router-dom";

const SolutionSection = () => {
//   const [data, setData] = useState(null);

//   useEffect(() => {
//     loadMarkdown("/content/home/solution.md").then(setData);
//   }, []);

//   if (!data) return null;

//   return (
//     <section className="solution py-5 px-3 d-flex justify-content-between align-items-center">
//       <div className="solution-text max-w-xl">
//         <h2 className="h2 fw-bold mb-4">{data.frontmatter.title}</h2>
//         <ul className="list-unstyled">
//           {data.frontmatter.points.map((point, idx) => (
//             <li key={idx} className="text-dark">
//               • {point}
//             </li>
//           ))}
//         </ul>
//       </div>
//       {data.frontmatter.image && (
//         <div className="solution-img">
//           <img
//             src={data.frontmatter.image}
//             alt="Solution"
//             className="img-fluid w-75"
//           />
//         </div>
//       )}
//     </section>
//   );
  const [data, setData] = useState(null);

  useEffect(() => {
    loadMarkdown("/content/home/solution.md").then(setData);
  }, []);

  if (!data) return null;

  const { headline, description, cards, button } = data.frontmatter;

  return (
    <section className="tagline    tagline-container-padding">
      {/* Headline & Description */}
      <h2 className="display-3  text-center  fw-bold">{headline}</h2>
      
 

      {/* Cards */}
      <div className="container-fluid py-5">
        <div className="row">
          {cards?.map((card, index) => (
            index == 1 ? (
                    <div className="col-md-6 mb-4" key={index}>
                       <div className="card h-100 p-4 background-none border-0 ">
                          <img src={card.image} alt="" srcset="" />
                       </div>
                    </div> 
            ):(
                   <div className={` ${index == 0? " col-md-6 mb-4 d-flex align-items-end":" col-md-6 mb-4"} `} key={index}>
              <div className={` ${index == 0?"card       p-4  border-0 solution-card-bg":"card h-100 p-4  border-0 solution-card-bg"}  `}>
                {card.icon && <i className={`${card.icon} fa-2x mb-3`}></i>}
                <h5 className="fw-bold text-start">{card.title}</h5>
                <p className="text-muted text-start">{card.text}</p>
              </div>
            </div>
            )
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

export default SolutionSection;
