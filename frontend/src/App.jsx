import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import RepoNavigator from './components/RepoNavigator'
import { selectedFileContext } from './context/context'

function App() {
  const [count, setCount] = useState(0)
  const [selectedFile, setSelectedFile] = useState('');

  return (
    <>
    <selectedFileContext.Provider value={{ selectedFile, setSelectedFile }}>
      <RepoNavigator></RepoNavigator>
    </selectedFileContext.Provider>
    </>
  )
}

export default App
