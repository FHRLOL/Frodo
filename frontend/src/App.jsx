import { useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { FormatContext } from './context.js'
import { AuthProvider } from './context/AuthContext.jsx'
import Layout from './components/Layout.jsx'
import RoleGuard from './components/RoleGuard.jsx'
import ChatPage from './pages/ChatPage.jsx'
import TeacherActivity from './pages/TeacherActivity.jsx'
import TeacherMaterials from './pages/TeacherMaterials.jsx'
import TeacherAccess from './pages/TeacherAccess.jsx'

export default function App({ initialAuth = null }) {
  const [format, setFormat] = useState('full')

  return (
    <AuthProvider initialAuth={initialAuth}>
      <FormatContext.Provider value={{ format, setFormat }}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<ChatPage />} />
            <Route
              path="/teacher"
              element={
                <RoleGuard allowedRoles={['instructor']}>
                  <TeacherActivity />
                </RoleGuard>
              }
            />
            <Route
              path="/teacher/materials"
              element={
                <RoleGuard allowedRoles={['instructor']}>
                  <TeacherMaterials />
                </RoleGuard>
              }
            />
            <Route
              path="/teacher/access"
              element={
                <RoleGuard allowedRoles={['instructor']}>
                  <TeacherAccess />
                </RoleGuard>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </FormatContext.Provider>
    </AuthProvider>
  )
}
