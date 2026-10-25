import { useState, type MouseEvent } from 'react';
import { Icon } from './ui';

async function copy(text: string) {
  await navigator.clipboard.writeText(text);
}
export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [message, setMessage] = useState('');
  return (
    <span className="copy-action">
      <button
        type="button"
        className="button secondary small"
        onClick={() => {
          void copy(text)
            .then(() => setMessage('Copied'))
            .catch(() => setMessage('Select the text to copy'));
        }}
      >
        {label}
      </button>
      <span className="copy-feedback" aria-live="polite">
        {message}
      </span>
    </span>
  );
}
export function CodeBlock({ code, label = 'Commands' }: { code: string; label?: string }) {
  return (
    <div className="code-block">
      <CopyButton text={code} label="Copy commands" />
      <pre tabIndex={0} role="region" aria-label={label}>
        <code>{code}</code>
      </pre>
    </div>
  );
}
export function HtmlContent({ html }: { html: string }) {
  const [message, setMessage] = useState('');
  function handleCopy(event: MouseEvent<HTMLDivElement>) {
    const button = (event.target as Element).closest<HTMLButtonElement>('[data-copy-code]');
    if (!button) return;
    const code = button.closest('.code-block')?.querySelector('code')?.textContent;
    if (code == null) return;
    void copy(code)
      .then(() => {
        button.textContent = 'Copied';
        setMessage('Code copied to clipboard.');
      })
      .catch(() => setMessage('Select the code to copy it.'));
  }
  return (
    <>
      <div onClick={handleCopy} dangerouslySetInnerHTML={{ __html: html }} />
      <span className="sr-only" aria-live="polite">
        {message}
      </span>
    </>
  );
}
export function LoadNotice({
  loading,
  error,
  retry,
}: {
  loading: boolean;
  error: string;
  retry: () => void;
}) {
  if (error)
    return (
      <div className="notice error load-notice">
        <p role="alert">{error}</p>
        <button className="button secondary" onClick={retry}>
          <Icon name="reset" size={16} />
          Retry recording
        </button>
      </div>
    );
  return loading ? (
    <p className="notice" role="status">
      Loading the selected recording…
    </p>
  ) : null;
}
