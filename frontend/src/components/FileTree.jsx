import React, { useContext, useMemo, useState } from 'react';
import { selectedFileContext } from '../context/context';

function fileTypeLabel(fileName) {
  const ext = fileName.split('.').pop();
  if (!ext || ext === fileName) return 'FILE';
  return ext.slice(0, 4).toUpperCase();
}

function flattenTree(tree, basePath = '') {
  return Object.entries(tree || {}).flatMap(([name, subtree]) => {
    const fullPath = basePath ? `${basePath}/${name}` : name;
    const isFile = Object.keys(subtree || {}).length === 0;

    if (isFile) {
      return [{ name, path: fullPath }];
    }

    return flattenTree(subtree, fullPath);
  });
}

function TreeBranch({ tree, path = '', expandedFolders, onToggle }) {
  const { selectedFile, setSelectedFile } = useContext(selectedFileContext);

  return (
    <ul className="tree-list">
      {Object.entries(tree || {}).map(([name, subtree]) => {
        const fullPath = path ? `${path}/${name}` : name;
        const isFile = Object.keys(subtree || {}).length === 0;
        const isExpanded = expandedFolders[fullPath] ?? path === '';

        return (
          <li key={fullPath}>
            {isFile ? (
              <button
                className={`tree-file ${selectedFile === fullPath ? 'active' : ''}`}
                onClick={() => setSelectedFile(fullPath)}
                title={fullPath}
              >
                <span>{fileTypeLabel(name)}</span>
                <strong>{name}</strong>
              </button>
            ) : (
              <>
                <button className="tree-folder" onClick={() => onToggle(fullPath)}>
                  <span>{isExpanded ? '-' : '+'}</span>
                  <strong>{name}</strong>
                </button>

                {isExpanded && (
                  <div className="tree-children">
                    <TreeBranch
                      tree={subtree}
                      path={fullPath}
                      expandedFolders={expandedFolders}
                      onToggle={onToggle}
                    />
                  </div>
                )}
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default function FileTree({ tree }) {
  const { selectedFile, setSelectedFile } = useContext(selectedFileContext);
  const [expandedFolders, setExpandedFolders] = useState({});
  const [search, setSearch] = useState('');
  const files = useMemo(() => flattenTree(tree), [tree]);
  const matches = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return [];
    return files
      .filter((file) => file.path.toLowerCase().includes(needle))
      .slice(0, 12);
  }, [files, search]);

  const toggleFolder = (folderPath) => {
    setExpandedFolders((prev) => ({
      ...prev,
      [folderPath]: !(prev[folderPath] ?? false),
    }));
  };

  return (
    <div className="file-tree">
      <label className="tree-search">
        <span>Search files</span>
        <input
          type="search"
          placeholder="routes, package, auth..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>

      {search ? (
        <div className="search-results">
          {matches.length > 0 ? (
            matches.map((file) => (
              <button
                key={file.path}
                className={selectedFile === file.path ? 'active' : ''}
                onClick={() => setSelectedFile(file.path)}
                title={file.path}
              >
                <span>{fileTypeLabel(file.name)}</span>
                {file.path}
              </button>
            ))
          ) : (
            <p>No matching files found.</p>
          )}
        </div>
      ) : (
        <div className="tree-scroll">
          <TreeBranch
            tree={tree}
            expandedFolders={expandedFolders}
            onToggle={toggleFolder}
          />
        </div>
      )}
    </div>
  );
}
