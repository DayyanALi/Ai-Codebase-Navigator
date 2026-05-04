import { useState } from 'react';
import './App.css';
import RepoNavigator from './components/RepoNavigator';
import { selectedFileContext as SelectedFileContext } from './context/context';

function App() {
  const [selectedFile, setSelectedFile] = useState('');

  return (
    <SelectedFileContext.Provider value={{ selectedFile, setSelectedFile }}>
      <RepoNavigator />
    </SelectedFileContext.Provider>
  );
}

export default App;
