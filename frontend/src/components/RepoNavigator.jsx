/** @format */

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import FileTree from './FileTree';
import AnswerCard from './AnswerCard';

export default function RepoNavigator() {
  const [repoName, setRepoName] = useState('');
  const [branchName, setBranchName] = useState('main');
  const [sessionId, setSessionId] = useState(null);
  const [cloning, setCloning] = useState(false);
  const [cloneError, setCloneError] = useState('');

  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [querying, setQuerying] = useState(false);
  const [queryError, setQueryError] = useState('');
  const [connected, setConnected] = useState('#f00000');
  const [folderTree, setFolderTree] = useState(null);



  useEffect(() => {
    const checkConnection = async () => {
      try {
        const baseUrl =
          import.meta.env.VITE_APIGATEWAY_URI || 'http://localhost:5000';
        const res = await axios.get(`${baseUrl}/status`);
        if (res.data.message) {
          console.log('connected');
          setConnected('#008000');
        }
      } catch (error) {
        console.error('Error checking connection:', error);
      }
    };

    checkConnection();
  }, []);

  const handleClone = async () => {
    setCloning(true);
    setCloneError('');
    try {
      let finalRepoName = repoName.trim();
      let finalBranchName = branchName.trim() || 'main';

      // Auto-extract from URL if user pasted a full GitHub link
      // e.g. https://github.com/dayyanali/repo/tree/master
      if (finalRepoName.startsWith('http')) {
        try {
          const url = new URL(finalRepoName);
          const parts = url.pathname.split('/').filter(Boolean);
          if (parts.length >= 2) {
            finalRepoName = `${parts[0]}/${parts[1]}`;
            if (parts.length >= 4 && parts[2] === 'tree') {
              finalBranchName = parts[3];
            }
          }
        } catch (e) {
          // ignore URL parse errors and fall back to whatever they typed
        }
      }

      setRepoName(finalRepoName); // update UI to show extracted name
      setBranchName(finalBranchName);

      const baseUrl =
        import.meta.env.VITE_APIGATEWAY_URI || 'http://localhost:5000';
      const res = await axios.post(`${baseUrl}/clone`, { repo_name: finalRepoName, branch_name: finalBranchName });
      console.log('check res', res);
      if (res.data.error) {
        console.log('error', res.data.error);
        setCloneError(res.data.error);
      } else {
        setSessionId(res.data.session_id);
        if (res.data.folder_structure) {
          setFolderTree(res.data.folder_structure);
        }
        console.log('session id set', res.data.session_id);
      }
    } catch (e) {
      const backendErr = e.response?.data?.error;
      setCloneError(backendErr || e.message || 'Error cloning repository');
    } finally {
      setCloning(false);
    }
  };

  const handleAsk = async () => {
    setQuerying(true);
    setQueryError('');
    try {
      const baseUrl =
        import.meta.env.VITE_APIGATEWAY_URI || 'http://localhost:5000';
      console.log('base', baseUrl);
      const res = await axios.post(`${baseUrl}/query`, {
        session_id: sessionId,
        question: question,
      });
      if (res.data.error) {
        setQueryError(res.data.error);
      } else {
        setAnswer(res.data.answer);
        setQuestion("");
      }
    } catch (e) {
      const backendErr = e.response?.data?.error;
      setQueryError(backendErr || e.message || 'Error fetching answer');
    } finally {
      setQuerying(false);
    }
  };

  const removeRepo = async () => {
    try {
      setSessionId(null);
      setAnswer('');
      setSources([]);
      setRepoName('');
      const baseURL = import.meta.env.VITE_APIGATEWAY_URI || 'http://localhost:5000';
      await axios.post(`${baseURL}/remove_repo`, { session_id: sessionId });
    } catch (e) {
      console.error('Error removing repository:', e);
    }
  };

  return (
    <div className='min-h-screen bg-[#555677] flex justify-center items-center p-4'>
      <div className='bg-[#223377] p-6 rounded-2xl w-full max-w-3xl space-y-6'>
        {!sessionId ? (
          <div className='space-y-6'>
            <h1 className='text-4xl font-semibold text-white'>
              Ai Codebase Navigator
            </h1>
            <svg width='64' height='64'>
              <circle cx='32' cy='32' r='8' fill={connected} />
            </svg>
            <p className='text-gray-400'>Enter the name of the GitHub repository (e.g. facebook/react) or paste the full GitHub URL.</p>
            <input
              type='text'
              placeholder='GitHub repo name or URL (e.g. https://github.com/facebook/react)'
              className='mb-4 w-full p-2 border border-gray-300 rounded-2xl text-white'
              value={repoName}
              onChange={(e) => setRepoName(e.target.value)}
            />
            <input
              type='text'
              placeholder='Branch name (optional, defaults to main or extracts from URL)'
              className='mb-4 w-full p-2 border border-gray-300 rounded-2xl text-white'
              value={branchName}
              onChange={(e) => setBranchName(e.target.value)}
            />
            <button
              onClick={handleClone}
              disabled={cloning || !repoName}
              className='px-4 py-2 bg-[#ff000f] text-white rounded-2xl disabled:opacity-50'
            >
              {cloning ? 'Adding...' : 'Add'}
            </button>
            {cloneError && <p className='text-red-300'>{cloneError}</p>}
          </div>
        ) : (
          <div className='space-y-4'>
            <h1 className='text-2xl font-semibold text-white'>
              Ask a Question
            </h1>
            {folderTree && (
              <div className='bg-zinc-800/80 p-5 rounded-2xl border border-zinc-700 shadow-sm text-zinc-100'>
                <h2 className='text-lg font-semibold mb-3 text-white'>File Explorer</h2>
                <div className='max-h-64 overflow-y-auto pr-2 custom-scrollbar'>
                  <FileTree tree={folderTree} />
                </div>
              </div>
            )}
            <textarea
              rows={4}
              placeholder='Ask about the code...'
              className='w-full p-4 border border-zinc-600 rounded-2xl bg-zinc-700/50 text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all resize-none shadow-inner'
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <div className='flex items-center gap-4'>
              <button
                onClick={handleAsk}
                disabled={querying || !question}
                className='px-6 py-2.5 bg-sky-600 hover:bg-sky-500 text-white font-medium rounded-xl disabled:opacity-50 transition-colors shadow-sm'
              >
                {querying ? 'Thinking...' : 'Ask'}
              </button>
              {queryError && <p className='text-red-400 text-sm'>{queryError}</p>}
            </div>
            {answer && (
              <div className="mt-8 animate-fade-in relative">
                <div className="absolute -left-3 top-0 bottom-0 w-1 bg-sky-500 rounded-full"></div>
                <h2 className='text-xl font-semibold text-white mb-4 pl-2'>Answer</h2>
                <AnswerCard markdown={answer} />
              </div>
            )}
            <div className='pt-6 mt-4 border-t border-zinc-700/50'>
              <button
                onClick={removeRepo}
                className='px-5 py-2 bg-rose-600/20 hover:bg-rose-600/40 text-rose-400 border border-rose-600/30 rounded-xl transition-colors font-medium text-sm'
              >
                Remove Repo
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
