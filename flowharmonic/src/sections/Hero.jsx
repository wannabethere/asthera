// import React, { useEffect, useState } from "react";
// import { loadMarkdown } from "../utils/loadMarkdown";

// const Hero = () => {
//   const [data, setData] = useState(null);

//   useEffect(() => {
//     loadMarkdown("/content/home/hero.md").then(setData);
//   }, []);

//   if (!data) return null;

//   const { headline, subtext, cta1, cta2, image } = data.frontmatter;

//   return (
//     <section className="hero flex items-center justify-between p-12 bg-black text-white">
//       <div className="hero-text max-w-lg">
//         <h1 className="text-4xl font-bold">{headline}</h1>
//         <p className="mt-4 text-lg">{subtext}</p>
//         <button className="mt-6 px-6 py-3 bg-blue-600 rounded-md">
//           {cta1}
//         </button>
//         <button className="mt-6 px-6 py-3 bg-blue-600 rounded-md">
//           {cta2}
//         </button>
//       </div>
//       {image && (
//         <video autoPlay muted loop playsInline className="">
//           <source src={image} type="video/mp4" />
//           Your browser does not support the video tag
//         </video>
//       )}
//     </section>
//   );
// };

// export default Hero;
import React, { useEffect, useState } from "react";
import { loadMarkdown } from "../utils/loadMarkdown";
import { Container, Row, Col, Button } from "react-bootstrap";
import { useNavigate } from "react-router-dom";

const Hero = () => {
  const [data, setData] = useState(null);
  const navigate = useNavigate(); // for redirection

  useEffect(() => {
    loadMarkdown("/content/home/hero.md").then(setData);
  }, []);

  if (!data) return null;

  const { headline, subtext, cta1, cta1Link, cta2, cta2Link, image } = data.frontmatter;

  return (
    <section className="hero py-5 bg-dark text-white home-page-hero-container">
      <Container>
        <Row className="align-items-center">
          {/* Left Text Content */}
          <Col md={6}>
            <h1 className="display-3 fw-bold">{headline}</h1>
            <p className="fs-small">{subtext}</p>
            <div className="mt-4">
              {cta1 && (
                <Button
                  variant="primary"
                  className="me-2"
                  onClick={() => cta1Link && navigate(cta1Link)}
                >
                  {cta1}
                </Button>
              )}
              {cta2 && (
                <Button
                  variant="secondary"
                  onClick={() => cta2Link && navigate(cta2Link)}
                >
                  {cta2}
                </Button>
              )}
            </div>
          </Col>

          {/* Right Video */}
          <Col md={6}>
            {image && (
            //   <video
            //     autoPlay
            //     muted
            //     loop
            //     playsInline
            //     className="w-100 rounded"
            //   >
            //     <source src={image} type="video/mp4" />
            //     Your browser does not support the video tag
            //   </video>
            <img src={image} alt="Hero-Image"   className="w-100 rounded homepage-hero-img floating" />
            )}
          </Col>
        </Row>
      </Container>
    </section>
  );
};

export default Hero;
 