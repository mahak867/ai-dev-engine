import React from "react"
import { Link, useNavigate } from "react-router-dom"
export default function Navbar({ user, onLogout }) {
  const nav = useNavigate()
  const logout = () => { if(onLogout) onLogout(); nav("/login") }
  return (
    <nav className="navbar">
      <div className="navbar-logo">App</div>
      <div className="navbar-links">
        {user ? (<>
          <Link to="/">Home</Link>
          <Link to="/dashboard">Dashboard</Link>
          <span style={{color:"var(--text-secondary)"}}>{user.name||user.email||"User"}</span>
          <button className="btn-secondary" onClick={logout}>Logout</button>
        </>) : (<>
          <Link to="/login">Login</Link>
          <Link to="/register"><button className="btn-primary">Get Started</button></Link>
        </>)}
      </div>
    </nav>
  )
}
