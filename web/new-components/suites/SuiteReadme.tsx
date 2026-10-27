import { FileTextOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import styles from './SuiteReadme.module.css';

type SuiteReadmeProps = {
  children: string;
  label: string;
};

export default function SuiteReadme({ children, label }: SuiteReadmeProps) {
  return (
    <section className={styles.card} aria-label={label} data-testid='suite-readme'>
      <div className={styles.label}>
        <FileTextOutlined aria-hidden />
        <span>{label}</span>
      </div>
      <div className={styles.content}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ children, href }) => (
              <a href={href} target='_blank' rel='noreferrer'>
                {children}
              </a>
            ),
            table: ({ children }) => (
              <div className={styles.tableScroll}>
                <table>{children}</table>
              </div>
            ),
          }}
        >
          {children}
        </ReactMarkdown>
      </div>
    </section>
  );
}
