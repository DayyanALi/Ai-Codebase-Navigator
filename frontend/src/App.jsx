import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import RepoNavigator from './components/RepoNavigator'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <RepoNavigator></RepoNavigator>
    </>
  )
}

export default App
