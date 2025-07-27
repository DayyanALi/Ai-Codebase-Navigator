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
          <li key={fullPath} className="my-1">
            {isFile ? (
              <button
                className={`text-blue-200 hover:underline ${selectedFile === fullPath ? 'font-bold' : ''}`}
                onClick={() => setSelectedFile(fullPath)}
              >
                📄 {name}
              </button>
            ) : (
              <div>
                <button
                  className="text-white hover:text-yellow-400 font-semibold mr-2"
                  onClick={() => toggleFolder(fullPath)}
                >
                  {isExpanded ? '-' : '+'} {name}/
                </button>
                {isExpanded && (
                  <FileTree tree={subtree} path={fullPath} />
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
