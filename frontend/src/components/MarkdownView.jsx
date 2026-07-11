import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

// Renders markdown WITH LaTeX math (spec 07 §1). Inline `$…$` and block `$$…$$` are
// typeset by KaTeX so equations like $V^\pi(s)$ display properly instead of raw source.
export default function MarkdownView({ children }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
      >
        {children || ""}
      </ReactMarkdown>
    </div>
  );
}
