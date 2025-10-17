


// import React, { useState, useRef, useEffect } from "react";
// import { FiChevronDown, FiChevronUp, FiCalendar, FiMail } from "react-icons/fi";
// import "../style/header.css";

// const Header = () => {
//   const [isNavCollapsed, setIsNavCollapsed] = useState(true);
//   const [openDropdown, setOpenDropdown] = useState(null);
//   const navRef = useRef(null);

//   const handleNavCollapse = () => setIsNavCollapsed(!isNavCollapsed);

//   const toggleDropdown = (menu) => {
//     setOpenDropdown(openDropdown === menu ? null : menu);
//   };

//   // Close dropdown when clicking outside
//   useEffect(() => {
//     const handleClickOutside = (event) => {
//       if (navRef.current && !navRef.current.contains(event.target)) {
//         setOpenDropdown(null);
//       }
//     };

//     document.addEventListener("mousedown", handleClickOutside);
//     return () => document.removeEventListener("mousedown", handleClickOutside);
//   }, []);

//   return (
//     <nav
//       ref={navRef}
//       className="navbar navbar-expand-lg navbar-light bg-white shadow-sm sticky-top"
//     >
//       <div className="container-fluid px-5 d-flex justify-content-between align-items-center">
//         {/* Brand */}
//         <a className="navbar-brand fw-bold fs-4" href="">
//           <span style={{ color: "rgb(239, 87, 19)" }}>LexyNeural</span>
//         </a>

//         {/* Mobile Toggle */}
//         <button
//           className="navbar-toggler"
//           type="button"
//           onClick={handleNavCollapse}
//         >
//           <span className="navbar-toggler-icon"></span>
//         </button>

//         {/* Navbar Items */}
//         <div
//           className={`${isNavCollapsed ? "collapse" : ""} navbar-collapse`}
//           style={{ flexGrow: 1 }}
//         >
//           <ul className="navbar-nav mx-auto mb-2 mb-lg-0">
//             {/* Products Dropdown */}
//             <li className="nav-item dropdown position-relative">
//               <button
//                 className="nav-link text-dark d-flex align-items-center border-0 bg-transparent"
//                 onClick={() => toggleDropdown("products")}
//               >
//                 Products
//                 {openDropdown === "products" ? (
//                   <FiChevronUp className="ms-1" />
//                 ) : (
//                   <FiChevronDown className="ms-1" />
//                 )}
//               </button>
//               <ul
//                 className={`dropdown-menu ${
//                   openDropdown === "products" ? "show" : ""
//                 }`}
//               >
//                 <li>
//                   <a className="dropdown-item text-dark" href="">
//                     LexyAI Assistant
//                   </a>
//                 </li>
//                 <li>
//                   <a className="dropdown-item text-dark" href="">
//                     NeuralAPI
//                   </a>
//                 </li>
//                 <li>
//                   <a className="dropdown-item text-dark" href="">
//                     SmartChat Widget
//                   </a>
//                 </li>
//                 <li>
//                   <a className="dropdown-item text-dark" href="">
//                     Insights Dashboard
//                   </a>
//                 </li>
//               </ul>
//             </li>

//             {/* Solutions Dropdown */}
//             <li className="nav-item dropdown position-relative">
//               <button
//                 className="nav-link text-dark d-flex align-items-center border-0 bg-transparent"
//                 onClick={() => toggleDropdown("solutions")}
//               >
//                 Solutions
//                 {openDropdown === "solutions" ? (
//                   <FiChevronUp className="ms-1" />
//                 ) : (
//                   <FiChevronDown className="ms-1" />
//                 )}
//               </button>
//               <ul
//                 className={`dropdown-menu ${
//                   openDropdown === "solutions" ? "show" : ""
//                 }`}
//               >
//                 <li>
//                   <a className="dropdown-item text-dark" href="">
//                     Customer Support Automation
//                   </a>
//                 </li>
//                 <li>
//                   <a className="dropdown-item text-dark" href="">
//                     Sales Enablement
//                   </a>
//                 </li>
//                 <li>
//                   <a className="dropdown-item text-dark" href="">
//                     Knowledge Management
//                   </a>
//                 </li>
//               </ul>
//             </li>

//             {/* Other Nav Items */}
//             <li className="nav-item">
//               <a className="nav-link text-dark" href="">
//                 Customer Stories
//               </a>
//             </li>
//           </ul>

//           {/* Right-side Buttons */}
//           <div className="d-flex">
//             <button className="btn btn-primary me-2 d-flex align-items-center">
//               <FiCalendar className="me-1" /> Book a Demo
//             </button>
//             <button className="btn btn-outline-dark contact-btn d-flex align-items-center">
//               <FiMail className="me-1" /> <a href="mailto:info@lexyneural.com" className="text-decoration-none ">Contact</a> 
//             </button>
//           </div>
//         </div>
//       </div>
//     </nav>
//   );
// };

// export default Header;
import React, { useState, useRef, useEffect } from "react";
import { FiChevronDown, FiChevronUp, FiCalendar, FiMail } from "react-icons/fi";
import "../style/header.css";
import { Link } from "react-router-dom";

const Header = () => {
  const [isNavCollapsed, setIsNavCollapsed] = useState(true);
  const [openDropdown, setOpenDropdown] = useState(null);

  const handleNavCollapse = () => setIsNavCollapsed(!isNavCollapsed);

  // Check if mobile screen (hover not good for touch devices)
  const isMobile = window.innerWidth < 992;

  const handleMouseEnter = (menu) => {
    if (!isMobile) setOpenDropdown(menu);
  };

  const handleMouseLeave = () => {
    if (!isMobile) setOpenDropdown(null);
  };

  const toggleDropdown = (menu) => {
    if (isMobile) setOpenDropdown(openDropdown === menu ? null : menu);
  };

  return (
    <nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm sticky-top">
      <div className="container-fluid px-5 d-flex justify-content-between align-items-center">
        {/* Brand */}
        <Link className="navbar-brand fw-bold fs-4" to={"/"}>
          <span style={{ color: "rgb(239, 87, 19)" }}>Lexy</span>
          <img src="" alt="" srcset="" />
        </Link>

        {/* Mobile Toggle */}
        <button
          className="navbar-toggler"
          type="button"
          onClick={handleNavCollapse}
        >
          <span className="navbar-toggler-icon"></span>
        </button>

        {/* Navbar Items */}
        <div
          className={`${isNavCollapsed ? "collapse" : ""} navbar-collapse`}
          style={{ flexGrow: 1 }}
        >
          <ul className="navbar-nav mx-auto mb-2 mb-lg-0">
            {/* Products Dropdown */}
            <li
              className="nav-item dropdown position-relative"
              onMouseEnter={() => handleMouseEnter("products")}
              onMouseLeave={handleMouseLeave}
            >
              <button
                className="nav-link text-dark d-flex align-items-center border-0 bg-transparent"
                onClick={() => toggleDropdown("products")}
              >
                What is Lexy
                {openDropdown === "products" ? (
                  <FiChevronUp className="ms-1" />
                ) : (
                  <FiChevronDown className="ms-1" />
                )}
              </button>
              <ul
                className={`dropdown-menu ${
                  openDropdown === "products" ? "show" : ""
                }`}
              >
                <li>
                  <Link to={'/platform'}  className="dropdown-item text-dark" >
                    Platform
                  </Link>
                </li>
                <li>
                  <a className="dropdown-item text-dark" href="">
                    Architecture
                  </a>
                </li>
                <li>
                  <a className="dropdown-item text-dark" href="">
                   Agentic Difference 
                  </a>
                </li>
                {/* <li>
                  <a className="dropdown-item text-dark" href="">
                    Insights Dashboard
                  </a>
                </li> */}
              </ul>
            </li>

            {/* product dropdwon  */}

            {/* <li className="nav-item">
              <a className="nav-link text-dark" href="">
                 Products
              </a>
            </li>  */}

               <li
              className="nav-item dropdown position-relative"
              onMouseEnter={() => handleMouseEnter("product")}
              onMouseLeave={handleMouseLeave}
            >
              <button
                className="nav-link text-dark d-flex align-items-center border-0 bg-transparent"
                onClick={() => toggleDropdown("product")}
              >
                products
                {openDropdown === "product" ? (
                  <FiChevronUp className="ms-1" />
                ) : (
                  <FiChevronDown className="ms-1" />
                )}
              </button>
              <ul
                className={`dropdown-menu ${
                  openDropdown === "product" ? "show" : ""
                }`}
              >
                <li>
                  <a className="dropdown-item text-dark" href="">
                    Strategic Insights for HR
                  </a>
                </li> 
              </ul>
            </li>

            {/* Solutions Dropdown */}
            <li
              className="nav-item dropdown position-relative"
              onMouseEnter={() => handleMouseEnter("solutions")}
              onMouseLeave={handleMouseLeave}
            >
              <button
                className="nav-link text-dark d-flex align-items-center border-0 bg-transparent"
                onClick={() => toggleDropdown("solutions")}
              >
                Resources
                {openDropdown === "solutions" ? (
                  <FiChevronUp className="ms-1" />
                ) : (
                  <FiChevronDown className="ms-1" />
                )}
              </button>
              <ul
                className={`dropdown-menu ${
                  openDropdown === "solutions" ? "show" : ""
                }`}
              >
                <li>
                  <a className="dropdown-item text-dark" href="">
                    Blogs
                  </a>
                </li>
                <li>
                  <a className="dropdown-item text-dark" href="">
                   Case Studies
                  </a>
                </li>
                <li>
                  <a className="dropdown-item text-dark" href="">
                     White Paper
                  </a>
                </li>
              </ul>
            </li>

              <li className="nav-item">
              <a className="nav-link text-dark" href="">
                 Company
              </a>
            </li>

            {/* Other Nav Items */}
            {/* <li className="nav-item">
              <a className="nav-link text-dark" href="">
                Customer Stories
              </a>
            </li> */}
          </ul>

          {/* Right-side Buttons */}
          <div className="d-flex">
            <button className="btn btn-primary me-2 d-flex align-items-center">
              <FiCalendar className="me-1" /> Book a Demo
            </button>
            <button className="btn btn-outline-dark d-flex align-items-center">
              <FiMail className="me-1" /> Contact
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Header;
