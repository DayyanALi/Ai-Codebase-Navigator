/** @format */

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import FileTree from './FileTree';

export default function RepoNavigator() {
  const [repoName, setRepoName] = useState('');
  const [branchName, setBranchName] = useState('');
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
      const baseUrl =
        import.meta.env.VITE_APIGATEWAY_URI || 'http://localhost:5000';
      const res = await axios.post(`${baseUrl}/clone`, { repo_name: repoName, branch_name: branchName });
      console.log('check res', res);
      if (res.data.error) {
        console.log('error', res.data.error);
        setCloneError('Error cloning repository');
      } else {
        setSessionId(res.data.session_id);
        if (res.data.folder_structure) {
          setFolderTree(res.data.folder_structure);
        }
        console.log('session id set', res.data.session_id);
      }
    } catch (e) {
      setCloneError(e.message || 'Error cloning repository');
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
      setAnswer(res.data.answer);
      //   setSources(res.data.sources);
    } catch (e) {
      setQueryError(e.message || 'Error fetching answer');
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
    } catch (e) {
      console.error('Error removing repository:', e);
    }
  };

  return (
    <div className='min-h-screen bg-[#ffffdd] flex justify-center items-center p-4'>
      <div className='bg-[#223377] p-6 rounded-2xl w-full max-w-3xl space-y-6'>
        {!sessionId ? (
          <div className='space-y-6'>
            <h1 className='text-4xl font-semibold text-white'>
              Ai Codebase Navigator
            </h1>
            <svg width='64' height='64'>
              <circle cx='32' cy='32' r='8' fill={connected} />
            </svg>
            <p className='text-gray-400'>Enter the URL of the GitHub repository you want to clone.</p>
            <input
              type='text'
              placeholder='GitHub repo name'
              className='mb-4 w-full p-2 border border-gray-300 rounded-2xl text-white'
              value={repoName}
              onChange={(e) => setRepoName(e.target.value)}
            />
            <input
              type='text'
              placeholder='Branch name'
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
              <div className='bg-gray-800 p-4 rounded text-white'>
                <h2 className='text-lg font-semibold mb-2'>File Explorer</h2>
                <FileTree tree={folderTree} />
              </div>
            )}
            <textarea
              rows={3}
              placeholder='Ask about the code...'
              className='w-full p-2 border border-gray-300 rounded text-white'
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <button
              onClick={handleAsk}
              disabled={querying || !question}
              className='px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50'
            >
              {querying ? 'Thinking...' : 'Ask'}
            </button>
            {queryError && <p className='text-red-300'>{queryError}</p>}
            {answer && (
              <div className='mt-6 bg-white p-4 rounded'>
                <h2 className='text-xl font-semibold'>Answer</h2>
                <p className='mt-2'>{answer}</p>
              </div>
            )}
            <div>
              <button
                onClick={removeRepo}
                className='px-4 py-2 bg-red-500 text-white rounded'
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
