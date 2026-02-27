import React, { useState, useContext } from 'react';
import { selectedFileContext } from '../context/context';

const FileTree = ({ tree, path = '' }) => {
  const { selectedFile, setSelectedFile } = useContext(selectedFileContext);
  const [expandedFolders, setExpandedFolders] = useState({});

  const toggleFolder = (folderPath) => {
    setExpandedFolders((prev) => ({
      ...prev,
      [folderPath]: !prev[folderPath],
    }));
  };

  return (
    <ul className="text-white ml-4">
      {Object.entries(tree).map(([name, subtree]) => {
        const fullPath = path ? `${path}/${name}` : name;
        const isFile = Object.keys(subtree).length === 0;
        const isExpanded = expandedFolders[fullPath];

        return (
          <li key={fullPath} className="my-1.5">
            {isFile ? (
              <button
                className={`flex items-center text-sm transition-colors ${selectedFile === fullPath ? 'font-bold text-sky-400' : 'text-zinc-300 hover:text-sky-300'}`}
                onClick={() => setSelectedFile(fullPath)}
              >
                <span className="mr-2 opacity-70">📄</span>
                {name}
              </button>
            ) : (
              <div>
                <button
                  className="flex items-center text-sm font-medium text-zinc-100 hover:text-white transition-colors"
                  onClick={() => toggleFolder(fullPath)}
                >
                  <span className="mr-2 w-4 text-center font-bold opacity-70 cursor-pointer text-zinc-400">
                    {isExpanded ? '▼' : '▶'}
                  </span>
                  <span className="mr-1.5 opacity-80">📁</span>
                  {name}
                </button>
                {isExpanded && (
                  <div className="ml-2 border-l border-zinc-700/50 pl-2 mt-1">
                    <FileTree tree={subtree} path={fullPath} />
                  </div>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
};

export default FileTree;
