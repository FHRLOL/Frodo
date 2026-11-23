import Logo from './Logo.jsx'

export default function Topbar({ title, children }) {
  return (
    <header className="topbar">
      <span className="topbar-title">{title}</span>
      <span className="topbar-brand">
        <Logo small />
      </span>
      <div className="topbar-right">{children}</div>
    </header>
  )
}
