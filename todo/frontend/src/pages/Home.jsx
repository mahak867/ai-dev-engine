import React from "react"
export default function Home() {
  const stats = [
    {label:"Total",value:"1,284",icon:"📊",change:"+12%"},
    {label:"Active",value:"342",icon:"⚡",change:"+24%"},
    {label:"Revenue",value:"$48k",icon:"💰",change:"+8%"},
    {label:"Uptime",value:"99.9%",icon:"✅",change:"stable"},
  ]
  return (
    <div className="page">
      <div style={{marginBottom:"32px"}}>
        <h1 style={{fontFamily:"serif",fontSize:"2rem",fontWeight:"700",marginBottom:"6px"}}>Dashboard</h1>
        <p style={{color:"var(--text-secondary)"}}>Welcome back.</p>
      </div>
      <div className="grid" style={{marginBottom:"32px"}}>
        {stats.map((s,i)=>(
          <div className="card animate-in" key={i} style={{animationDelay:`${i*0.08}s`}}>
            <div style={{display:"flex",justifyContent:"space-between",marginBottom:"12px"}}>
              <span style={{fontSize:"1.5rem"}}>{s.icon}</span>
              <span className="badge badge-success">{s.change}</span>
            </div>
            <div style={{fontSize:"2rem",fontWeight:"700",color:"var(--accent)",marginBottom:"4px"}}>{s.value}</div>
            <div style={{fontSize:"0.75rem",color:"var(--text-muted)",textTransform:"uppercase",letterSpacing:"0.06em"}}>{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}