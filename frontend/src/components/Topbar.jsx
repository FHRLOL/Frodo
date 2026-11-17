import Logo from './Logo.jsx'
import UserIndicator from './UserIndicator.jsx'

export default function Topbar({ title, children }) {
  return (
    <header className="topbar">
      <span className="topbar-title">{title}</span>
      <span className="topbar-brand">
        <Logo small />
      </span>
      <div className="topbar-right">
        {children}
        <UserIndicator compact />
      </div>
    </header>
  )
}
