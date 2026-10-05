import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function StructuredValue({ value }: { value: unknown }) {
    if (value === null || value === undefined) return <span>—</span>;
    if (Array.isArray(value)) return <ul>{value.map((entry, i) => <li key={i}><StructuredValue value={entry} /></li>)}</ul>;
    if (typeof value === 'object') return <dl>{Object.entries(value).map(([key, entry]) => <div key={key}><dt>{key.replace(/_/g, ' ')}</dt><dd><StructuredValue value={entry} /></dd></div>)}</dl>;
    return <ReactMarkdown remarkPlugins={[remarkGfm]}>{String(value)}</ReactMarkdown>;
}
export default function Explanation({ content }: { content: unknown }) {
    let parsed = content;
    if (typeof content === 'string') { try { parsed = JSON.parse(content); } catch { /* Preserve prose verbatim. */ } }
    return <div className="explanation"><StructuredValue value={parsed} /><details><summary>Ver datos técnicos</summary><pre>{typeof content === 'string' ? content : JSON.stringify(content, null, 2)}</pre></details></div>;
}
