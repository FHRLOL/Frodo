import { Link } from 'react-router-dom'

export default function Logo({ small = false }) {
  return (
    <Link to="/" className={small ? 'brand brand--sm' : 'brand'} aria-label="Frodo — на главную">
      <span className="brand-mark" aria-hidden="true">
        F
      </span>
      <span className="brand-name">Frodo</span>
    </Link>
  )
}