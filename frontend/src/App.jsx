import { useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { FormatContext } from './context.js'
import Layout from './components/Layout.jsx'
import ChatPage from './pages/ChatPage.jsx'
import TeacherActivity from './pages/TeacherActivity.jsx'
import TeacherMaterials from './pages/TeacherMaterials.jsx'
import TeacherAccess from './pages/TeacherAccess.jsx'

export default function App() {
  const [format, setFormat] = useState('full')

  return (
    <FormatContext.Provider value={{ format, setFormat }}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<ChatPage />} />
          <Route path="/teacher" element={<TeacherActivity />} />
          <Route path="/teacher/materials" element={<TeacherMaterials />} />
          <Route path="/teacher/access" element={<TeacherAccess />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </FormatContext.Provider>
  )
}