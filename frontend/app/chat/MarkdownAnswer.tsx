import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import styles from "./page.module.css";


export function MarkdownAnswer({ content }: { content: string }) {
  return (
    <div className={styles.markdown}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children, ...props }) => <div className={styles.tableWrap}><table {...props}>{children}</table></div>,
          a: ({ children, ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
