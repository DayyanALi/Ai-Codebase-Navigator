/** @format */

import React, { useCallback, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github-dark.css';

function CodeBlock({ children, lang }) {
  const [copied, setCopied] = useState(false);
  const text = String(children ?? '');
  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  }, [text]);

  return (
    <div className="code-block">
      <div className="code-toolbar">
        <span>{lang || 'code'}</span>
        <button onClick={copy}>{copied ? 'Copied' : 'Copy'}</button>
      </div>
      <pre>
        <code>{text}</code>
      </pre>
    </div>
  );
}

export default function AnswerCard({ markdown, sources = [] }) {
  const [copied, setCopied] = useState(false);

  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  return (
    <article className="answer-card">
      <div className="answer-card-header">
        <div>
          <p className="eyebrow">Navigator answer</p>
          <h2>Analysis</h2>
        </div>
        <button className="ghost-button" onClick={copyAnswer}>
          {copied ? 'Copied' : 'Copy answer'}
        </button>
      </div>

      <div className="markdown-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw, rehypeHighlight]}
          components={{
            h1: (props) => <h1 {...props} />,
            h2: (props) => <h2 {...props} />,
            h3: (props) => <h3 {...props} />,
            p: (props) => <p {...props} />,
            ul: (props) => <ul {...props} />,
            ol: (props) => <ol {...props} />,
            li: (props) => <li {...props} />,
            blockquote: (props) => <blockquote {...props} />,
            code: ({ inline, className, children, ...props }) => {
              const match = /language-(\w+)/.exec(className || '');
              if (inline) {
                return (
                  <code className="inline-code" {...props}>
                    {children}
                  </code>
                );
              }
              return <CodeBlock lang={match?.[1]}>{children}</CodeBlock>;
            },
            a: (props) => (
              <a target="_blank" rel="noopener noreferrer" {...props} />
            ),
            table: (props) => (
              <div className="table-wrap">
                <table {...props} />
              </div>
            ),
          }}
        >
          {markdown}
        </ReactMarkdown>
      </div>

      {sources.length > 0 && (
        <div className="source-list">
          <p className="eyebrow">Retrieved sources</p>
          {sources.map((source, index) => (
            <span key={`${source}-${index}`}>{String(source)}</span>
          ))}
        </div>
      )}
    </article>
  );
}
