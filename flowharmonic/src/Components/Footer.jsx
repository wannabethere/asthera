import React from 'react'
import '../style/footer.css'

const Footer = () => {
  return (
      <footer className=" footer-body text-white pt-5 pb-4">
        <div className="container">
          <div className="row">
            {/* Company Info */}
            <div className="col-md-4 mb-4">
              <h5 className="fw-bold mb-3" style={{color:"rgb(239, 87, 19)"}}>
                {/* <span className="bg-primary rounded-circle p-2 me-2">
                  <i className="fas fa-brain"></i>
                </span> */}
                LexyNeural
              </h5>
              <p className= " text-white    ">
                Building the next generation of AI-powered solutions for businesses and developers.
              </p>
              <div className="d-flex mt-3">
                <a href="#" className="text-white me-3">
                  <i className="fab fa-twitter fa-lg"></i>
                </a>
                <a href="#" className="text-white me-3">
                  <i className="fab fa-linkedin-in fa-lg"></i>
                </a>
                <a href="#" className="text-white me-3">
                  <i className="fab fa-github fa-lg"></i>
                </a>
                <a href="#" className="text-white">
                  <i className="fab fa-discord fa-lg"></i>
                </a>
              </div>
            </div>

            {/* Quick Links */}
            <div className="col-md-2 mb-4">
              <h5 className="fw-bold mb-3">Products</h5>
              <ul className="list-unstyled">
                <li className="mb-2"><a href="#" className="text-muted text-decoration-none">Strategic Insights for HR</a></li>
                {/* <li className="mb-2"><a href="#" className="text-muted text-decoration-none">NeuralAPI</a></li>
                <li className="mb-2"><a href="#" className="text-muted text-decoration-none">SmartChat</a></li>
                <li className="mb-2"><a href="#" className="text-muted text-decoration-none">Enterprise</a></li> */}
              </ul>
            </div>

            {/* Resources */}
            <div className="col-md-2 mb-4">
              <h5 className="fw-bold mb-3">Resources</h5>
              <ul className="list-unstyled">
                <li className="mb-2"><a href="#" className="text-muted text-decoration-none">Documentation</a></li>
                <li className="mb-2"><a href="#" className="text-muted text-decoration-none">Tutorials</a></li>
                <li className="mb-2"><a href="#" className="text-muted text-decoration-none">Blog</a></li>
                <li className="mb-2"><a href="#" className="text-muted text-decoration-none">Support</a></li>
              </ul>
            </div>

            {/* Contact */}
            <div className="col-md-4 mb-4">
              <h5 className="fw-bold mb-3">Stay Updated</h5>
              <p className="text-white">Subscribe to our newsletter for the latest updates</p>
              <div className="input-group mb-3">
                <input 
                  type="email" 
                  className="form-control bg-secondary border-0 text-white" 
                  placeholder="Your email" 
                />
                <button className="btn btn-primary" type="button">
                  Subscribe
                </button>
              </div>
              <div className="d-flex text-white">
                <div className="me-4">
                  <i className="fas fa-envelope me-2"></i>
                  <a className='text-decoration-none' href="mailto:info@lexyneural.com">contact@lexyneural.com</a>
                </div>
                <div>
                  <i className="fas fa-phone me-2"></i>
                  <span>+1 (555) 123-4567</span>
                </div>
              </div>
            </div>
          </div>

          {/* Copyright */}
          <div className="row pt-3 border-top border-secondary">
            <div className="col-md-6 text-center text-md-start">
              <p className="text-white mb-0">
                &copy; {new Date().getFullYear()} LexyNeural. All rights reserved.
              </p>
            </div>
            <div className="col-md-6 text-center text-md-end">
              <ul className="list-inline mb-0">
                <li className="list-inline-item">
                  <a href="#" className="text-white text-decoration-none">Privacy Policy</a>
                </li>
                <li className="list-inline-item mx-2">·</li>
                <li className="list-inline-item">
                  <a href="#" className="text-white text-decoration-none">Terms of Service</a>
                </li>
                <li className="list-inline-item mx-2">·</li>
                <li className="list-inline-item">
                  <a href="#" className="text-white text-decoration-none">Cookie Policy</a>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </footer>
  )
}

export default Footer