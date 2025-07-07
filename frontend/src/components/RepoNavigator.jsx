/** @format */

import React, { useEffect, useState } from 'react';
import axios from 'axios';

export default function RepoNavigator() {
  const [repoUrl, setRepoUrl] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [cloning, setCloning] = useState(false);
  const [cloneError, setCloneError] = useState('');

  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [querying, setQuerying] = useState(false);
  const [queryError, setQueryError] = useState('');
  const [connected, setConnected] = useState('#f00000');

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const baseUrl =
          import.meta.env.VITE_APIGATEWAY_URI || 'http://localhost:5000';
        const res = await axios.get(`${baseUrl}/status`);
        if (res.data.message) {
          console.log("connected")
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
      const res = await axios.post(`${baseUrl}/clone`, { repo_url: repoUrl });
      console.log('check res', res);
      if (res.data.error) {
        console.log('error', res.data.error);
        setCloneError("Error cloning repository");
      } else {
        setSessionId(res.data.session_id);
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
      // const baseUrl =
      //   import.meta.env.VITE_APIGATEWAY_URI || 'http://localhost:5000';
      // await axios.post(`${baseUrl}/remove`, { session_id: sessionId });
      setSessionId(null);
      setAnswer('');
      setSources([]);
      setRepoUrl('')
    } catch (e) {
      console.error('Error removing repository:', e);
    }
  };

  return (
    <div className='max-w-3xl mx-auto p-4'>
      {!sessionId ? (
        <div className='space-y-4'>
          <h1 className='text-2xl font-semibold'>Add a Repository</h1>
          <svg width='64' height='64'>
            <circle cx='32' cy='32' r='8' fill={connected} />
          </svg>

          <input
            type='text'
            placeholder='GitHub repo URL'
            className='mt-2 mb-4 w-full p-2 border rounded-2xl'
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
          />
          <button
            onClick={handleClone}
            disabled={cloning || !repoUrl}
            className='px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50'
          >
            {cloning ? 'Adding...' : 'Add'}
          </button>
          {cloneError && <p className='text-red-500'>{cloneError}</p>}
        </div>
      ) : (
        <div className='space-y-4'>
          <h1 className='text-2xl font-semibold'>Ask a Question</h1>
          <textarea
            rows={3}
            placeholder='Ask about the code...'
            className='w-full p-2 border rounded'
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <button
            onClick={handleAsk}
            disabled={querying || !question}
            className='px-4 py-2 bg-green-600 text-white rounded disabled:opacity-50'
          >
            {querying ? 'Thinking...' : 'Ask'}
          </button>
          {queryError && <p className='text-red-500'>{queryError}</p>}

          {answer && (
            <div className='mt-6'>
              <h2 className='text-xl font-semibold'>Answer</h2>
              <p className='p-4 rounded'>{answer}</p>
            </div>
          )}
          <div>
            <button onClick={removeRepo}>
              Remove Repo
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
