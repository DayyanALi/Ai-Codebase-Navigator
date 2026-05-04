/** @format */

import React, { useContext, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import FileTree from './FileTree';
import AnswerCard from './AnswerCard';
import { selectedFileContext } from '../context/context';

const baseUrl = import.meta.env.VITE_APIGATEWAY_URI || 'http://localhost:5000';

const starterQuestions = [
  'Give me a high-level architecture map of this repo.',
  'Where does the main request flow start and end?',
  'Which files should I read first to understand the project?',
  'Find likely bugs, risky code paths, and missing tests.',
];

const quickExamples = [
  { repo: 'octocat/Hello-World', branch: 'master' },
  { repo: 'sindresorhus/is', branch: 'main' },
  { repo: 'ai/nanoid', branch: 'main' },
];

const emptyStats = {
  files: 0,
  folders: 0,
  topLevel: 0,
};

function parseRepositoryInput(input, branch) {
  let finalRepoName = input.trim();
  let finalBranchName = branch.trim() || 'main';

  if (finalRepoName.startsWith('http')) {
    try {
      const url = new URL(finalRepoName);
      const parts = url.pathname.split('/').filter(Boolean);

      if (parts.length >= 2) {
        finalRepoName = `${parts[0]}/${parts[1].replace(/\.git$/, '')}`;
      }

      if (parts.length >= 4 && parts[2] === 'tree') {
        finalBranchName = parts[3];
      }
    } catch {
      // Keep the typed value if URL parsing fails.
    }
  }

  return { finalRepoName, finalBranchName };
}

function getTreeStats(tree) {
  if (!tree) return emptyStats;

  const walk = (node) => {
    return Object.values(node).reduce(
      (stats, subtree) => {
        const isFile = Object.keys(subtree || {}).length === 0;

        if (isFile) {
          return { ...stats, files: stats.files + 1 };
        }

        const childStats = walk(subtree);
        return {
          files: stats.files + childStats.files,
          folders: stats.folders + childStats.folders + 1,
          topLevel: stats.topLevel,
        };
      },
      { ...emptyStats, topLevel: Object.keys(node).length },
    );
  };

  return walk(tree);
}

function getRecentRepos() {
  try {
    return JSON.parse(localStorage.getItem('recentRepos') || '[]');
  } catch {
    return [];
  }
}

export default function RepoNavigator() {
  const { selectedFile, setSelectedFile } = useContext(selectedFileContext);
  const [repoName, setRepoName] = useState('');
  const [branchName, setBranchName] = useState('main');
  const [sessionId, setSessionId] = useState(null);
  const [cloning, setCloning] = useState(false);
  const [cloneError, setCloneError] = useState('');
  const [connectionState, setConnectionState] = useState('checking');

  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [querying, setQuerying] = useState(false);
  const [queryError, setQueryError] = useState('');
  const [folderTree, setFolderTree] = useState(null);
  const [queryHistory, setQueryHistory] = useState([]);
  const [recentRepos, setRecentRepos] = useState(getRecentRepos);

  const repoStats = useMemo(() => getTreeStats(folderTree), [folderTree]);
  const canClone = repoName.trim().length > 0 && !cloning;
  const canAsk = question.trim().length > 0 && sessionId && !querying;

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const res = await axios.get(`${baseUrl}/status`);
        setConnectionState(res.data.message ? 'online' : 'offline');
      } catch (error) {
        console.error('Error checking connection:', error);
        setConnectionState('offline');
      }
    };

    checkConnection();
  }, []);

  useEffect(() => {
    localStorage.setItem('recentRepos', JSON.stringify(recentRepos));
  }, [recentRepos]);

  const saveRecentRepo = (repo, branch) => {
    setRecentRepos((current) => {
      const next = [
        { repo, branch },
        ...current.filter((item) => item.repo !== repo || item.branch !== branch),
      ].slice(0, 4);

      return next;
    });
  };

  const handleClone = async () => {
    setCloning(true);
    setCloneError('');
    setAnswer('');
    setSources([]);
    setSelectedFile('');

    try {
      const { finalRepoName, finalBranchName } = parseRepositoryInput(
        repoName,
        branchName,
      );

      setRepoName(finalRepoName);
      setBranchName(finalBranchName);

      const res = await axios.post(`${baseUrl}/clone`, {
        repo_name: finalRepoName,
        branch_name: finalBranchName,
      });

      if (res.data.error) {
        setCloneError(res.data.error);
        return;
      }

      setSessionId(res.data.session_id);
      setFolderTree(res.data.folder_structure || null);
      saveRecentRepo(finalRepoName, finalBranchName);
    } catch (e) {
      const backendErr = e.response?.data?.error;
      setCloneError(backendErr || e.message || 'Error cloning repository');
    } finally {
      setCloning(false);
    }
  };

  const handleAsk = async (overrideQuestion) => {
    const rawQuestion = (overrideQuestion || question).trim();
    if (!rawQuestion) return;

    setQuerying(true);
    setQueryError('');

    try {
      const scopedQuestion = selectedFile
        ? `${rawQuestion}\n\nFocus on this file when relevant: ${selectedFile}`
        : rawQuestion;

      const res = await axios.post(`${baseUrl}/query`, {
        session_id: sessionId,
        question: scopedQuestion,
      });

      if (res.data.error) {
        setQueryError(res.data.error);
        return;
      }

      setAnswer(res.data.answer);
      setSources(res.data.sources || []);
      setQuestion('');
      setQueryHistory((current) =>
        [
          {
            question: rawQuestion,
            file: selectedFile,
            at: new Date().toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            }),
          },
          ...current,
        ].slice(0, 5),
      );
    } catch (e) {
      const backendErr = e.response?.data?.error;
      setQueryError(backendErr || e.message || 'Error fetching answer');
    } finally {
      setQuerying(false);
    }
  };

  const removeRepo = async () => {
    const activeSession = sessionId;

    setSessionId(null);
    setAnswer('');
    setSources([]);
    setQuestion('');
    setQueryError('');
    setCloneError('');
    setFolderTree(null);
    setSelectedFile('');

    try {
      if (activeSession) {
        await axios.post(`${baseUrl}/remove_repo`, { session_id: activeSession });
      }
    } catch (e) {
      console.error('Error removing repository:', e);
    }
  };

  const applyRecentRepo = (repo, branch) => {
    setRepoName(repo);
    setBranchName(branch);
  };

  const connectionCopy = {
    checking: 'Checking API',
    online: 'API online',
    offline: 'API offline',
  }[connectionState];

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">Repository intelligence workspace</p>
          <h1>Codebase Navigator</h1>
        </div>

        <div className={`status-pill ${connectionState}`}>
          <span aria-hidden="true" />
          {connectionCopy}
        </div>
      </section>

      {!sessionId ? (
        <section className="onboarding-grid">
          <div className="connect-card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">New analysis</p>
                <h2>Add repository</h2>
              </div>
              <span className="endpoint-label">{baseUrl}</span>
            </div>

            <label className="field">
              <span>GitHub repository</span>
              <input
                type="text"
                placeholder="facebook/react or https://github.com/facebook/react"
                value={repoName}
                onChange={(e) => setRepoName(e.target.value)}
              />
            </label>

            <label className="field">
              <span>Branch</span>
              <input
                type="text"
                placeholder="main"
                value={branchName}
                onChange={(e) => setBranchName(e.target.value)}
              />
            </label>

            {cloneError && <p className="error-banner">{cloneError}</p>}

            <button className="primary-action" onClick={handleClone} disabled={!canClone}>
              {cloning ? 'Indexing repository...' : 'Add repository'}
            </button>

            {recentRepos.length > 0 && (
              <div className="recent-block">
                <p>Recent repositories</p>
                <div className="recent-list">
                  {recentRepos.map((repo) => (
                    <button
                      key={`${repo.repo}-${repo.branch}`}
                      onClick={() => applyRecentRepo(repo.repo, repo.branch)}
                    >
                      {repo.repo}
                      <span>{repo.branch}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="intro-panel">
            <div>
              <p className="eyebrow">Workspace</p>
              <h2>Repository intake</h2>
            </div>

            <div className="intake-board" aria-label="Repository intake status">
              <div>
                <span>API</span>
                <strong>{connectionCopy}</strong>
              </div>
              <div>
                <span>Repository</span>
                <strong>{repoName.trim() || 'Not selected'}</strong>
              </div>
              <div>
                <span>Branch</span>
                <strong>{branchName.trim() || 'main'}</strong>
              </div>
              <div>
                <span>Session</span>
                <strong>{sessionId || 'Pending'}</strong>
              </div>
            </div>

            <div className="preset-panel">
              <p className="eyebrow">Quick examples</p>
              <div className="recent-list">
                {quickExamples.map((example) => (
                  <button
                    key={`${example.repo}-${example.branch}`}
                    onClick={() => {
                      setRepoName(example.repo);
                      setBranchName(example.branch);
                    }}
                  >
                    {example.repo}
                    <span>{example.branch}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>
      ) : (
        <section className="workspace-grid">
          <aside className="repo-sidebar">
            <div className="repo-card">
              <p className="eyebrow">Active repository</p>
              <h2>{repoName}</h2>
              <span>{branchName}</span>
            </div>

            <div className="stats-grid">
              <div>
                <strong>{repoStats.files}</strong>
                <span>Files</span>
              </div>
              <div>
                <strong>{repoStats.folders}</strong>
                <span>Folders</span>
              </div>
              <div>
                <strong>{repoStats.topLevel}</strong>
                <span>Top level</span>
              </div>
            </div>

            {folderTree && (
              <div className="explorer-panel">
                <div className="section-heading compact">
                  <div>
                    <p className="eyebrow">Repository map</p>
                    <h2>Files</h2>
                  </div>
                  {selectedFile && (
                    <button className="ghost-button" onClick={() => setSelectedFile('')}>
                      Clear
                    </button>
                  )}
                </div>
                <FileTree tree={folderTree} />
              </div>
            )}

            <button className="danger-action" onClick={removeRepo}>
              Remove repository
            </button>
          </aside>

          <section className="ask-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Agent workspace</p>
                <h2>Ask the codebase</h2>
              </div>
              {selectedFile && <span className="file-scope">Scoped: {selectedFile}</span>}
            </div>

            <div className="prompt-bar">
              {starterQuestions.map((prompt) => (
                <button key={prompt} onClick={() => setQuestion(prompt)}>
                  {prompt}
                </button>
              ))}
            </div>

            <textarea
              rows={6}
              placeholder="Ask about architecture, implementation details, call paths, tests, security risks, or a selected file..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                  handleAsk();
                }
              }}
            />

            <div className="action-row">
              <button className="primary-action" onClick={() => handleAsk()} disabled={!canAsk}>
                {querying ? 'Reasoning...' : 'Ask navigator'}
              </button>
              <span>Ctrl + Enter</span>
              {queryError && <p className="inline-error">{queryError}</p>}
            </div>

            {answer ? (
              <AnswerCard markdown={answer} sources={sources} />
            ) : (
              <div className="empty-answer">
                <p className="eyebrow">Ready when you are</p>
                <h3>Start with a system map, then drill into files and flows.</h3>
                <p>
                  Select a file from the explorer to scope the answer, or ask a
                  broad question to understand the whole repository.
                </p>
              </div>
            )}
          </section>

          <aside className="history-panel">
            <div className="section-heading compact">
              <div>
                <p className="eyebrow">Session trail</p>
                <h2>Recent questions</h2>
              </div>
            </div>

            {queryHistory.length > 0 ? (
              <div className="history-list">
                {queryHistory.map((item, index) => (
                  <button
                    key={`${item.at}-${index}`}
                    onClick={() => setQuestion(item.question)}
                  >
                    <span>{item.at}</span>
                    {item.question}
                    {item.file && <small>{item.file}</small>}
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted-copy">
                Questions you ask in this session will appear here for quick reuse.
              </p>
            )}
          </aside>
        </section>
      )}
    </main>
  );
}
