// components/AnswerCard.jsx
/** @format */
import React, { useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

function CodeBlock({ children, lang }) {
  const text = String(children ?? "");
  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {}
  }, [text]);

  return (
    <div className="group relative my-3 rounded-lg border border-zinc-700 bg-zinc-900">
      <div className="absolute right-2 top-2">
        <button
          onClick={copy}
          className="rounded-md bg-zinc-800 px-2 py-1 text-xs text-zinc-200 opacity-0 transition group-hover:opacity-100"
          title="Copy code"
        >
          Copy
        </button>
      </div>
      {lang && (
        <div className="px-3 pt-2 text-[10px] uppercase tracking-wide text-zinc-400">
          {lang}
        </div>
      )}
      <pre className="overflow-auto p-3 text-sm">
        <code>{text}</code>
      </pre>
    </div>
  );
}

export default function AnswerCard({ markdown }) {
  return (
    <div className="rounded-2xl border border-zinc-700 bg-zinc-800/60 p-4 text-zinc-100">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, rehypeHighlight]}
        components={{
          h2: ({ node, ...props }) => (
            <h2 className="mt-4 text-xl font-semibold text-white" {...props} />
          ),
          h3: ({ node, ...props }) => (
            <h3 className="mt-3 text-lg font-semibold text-white/90" {...props} />
          ),
          p: ({ node, ...props }) => (
            <p className="leading-7 text-zinc-200" {...props} />
          ),
          ul: ({ node, ...props }) => (
            <ul className="ml-5 list-disc space-y-1" {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ol className="ml-5 list-decimal space-y-1" {...props} />
          ),
          code: ({ inline, className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || "");
            if (inline) {
              return (
                <code
                  className="rounded bg-zinc-700/70 px-1.5 py-0.5 text-[90%]"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return <CodeBlock lang={match?.[1]}>{children}</CodeBlock>;
          },
          a: ({ node, ...props }) => (
            <a
              className="text-sky-400 underline hover:text-sky-300"
              {...props}
            />
          ),
          li: ({ node, ...props }) => <li className="text-zinc-200" {...props} />,
          table: ({ node, ...props }) => (
            <div className="overflow-x-auto">
              <table
                className="w-full border-collapse text-left"
                {...props}
              />
            </div>
          ),
          th: ({ node, ...props }) => (
            <th
              className="border-b border-zinc-700 px-3 py-2 font-medium"
              {...props}
            />
          ),
          td: ({ node, ...props }) => (
            <td
              className="border-b border-zinc-800 px-3 py-2 align-top"
              {...props}
            />
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
