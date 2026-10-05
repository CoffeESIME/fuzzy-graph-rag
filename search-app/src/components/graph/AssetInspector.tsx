import { useEffect, useRef, useState } from 'react';
import { X, PanelRightClose, PanelRightOpen, ExternalLink, Loader2 } from 'lucide-react';
import { getAssetPreview, type AssetPreviewResponse } from '../../lib/api';
import { TypeGlyph } from './GraphLegend';

export function AssetViewer({ asset }: { asset: AssetPreviewResponse }) {
    const player = useRef<HTMLMediaElement | null>(null);
    const source = asset.download_url || asset.minio_path;
    const mime = asset.mime_type ?? '';
    const extension = (asset.minio_path || source || '').split('?')[0].split('.').pop()?.toLowerCase();
    const kind = mime.startsWith('audio/') || ['mp3','wav','ogg','m4a','flac'].includes(extension ?? '') ? 'audio'
        : mime.startsWith('video/') || ['mp4','webm','mov'].includes(extension ?? '') ? 'video'
        : mime.startsWith('image/') || ['png','jpg','jpeg','webp','gif'].includes(extension ?? '') ? 'image'
        : mime === 'application/pdf' || extension === 'pdf' ? 'pdf' : 'text';
    const content = asset.content === 'No textual content available' ? '' : asset.content;
    const parts = content?.split(/(\b(?:\d{1,2}:)?\d{1,2}:\d{2}\b)/g) ?? [];
    return <div className="asset-viewer">
        {source && kind === 'audio' && <audio ref={el => { player.current = el; }} controls src={source} />}
        {source && kind === 'video' && <video ref={el => { player.current = el; }} controls src={source} />}
        {source && kind === 'image' && <img src={source} alt={asset.name} />}
        {source && kind === 'pdf' && <object data={source} type="application/pdf" aria-label={asset.name}><p>Vista PDF no disponible en este navegador.</p></object>}
        {source && <a href={source} target="_blank" rel="noopener noreferrer"><ExternalLink size={14} /> Abrir archivo original</a>}
        {content && <section><h4>Contenido extraído</h4><div className="asset-transcript">{parts.map((part, i) => (kind === 'audio' || kind === 'video') && /^\d{1,2}(?::\d{2}){1,2}$/.test(part)
            ? <button key={i} title={`Ir a ${part}`} onClick={() => { if (player.current) player.current.currentTime = part.split(':').reduce((n, value) => n * 60 + Number(value), 0); }}>{part}</button> : part)}</div></section>}
        <details><summary>Metadata técnica</summary><pre>{JSON.stringify({ id: asset.id, name: asset.name, type: asset.type, mime_type: asset.mime_type, tags: asset.tags, minio_path: asset.minio_path }, null, 2)}</pre></details>
    </div>;
}
export default function AssetInspector({ id, label, type, context, metadata, onClose }: {
    id: string; label: string; type: string; context: string[]; metadata?: unknown; onClose: () => void;
}) {
    const [asset, setAsset] = useState<AssetPreviewResponse | null>(null);
    const [status, setStatus] = useState(type === 'DigitalAsset' ? 'Cargando archivo…' : '');
    const [collapsed, setCollapsed] = useState(false);
    const dialog = useRef<HTMLDialogElement>(null);
    useEffect(() => {
        let active = true;
        if (type !== 'DigitalAsset') return;
        getAssetPreview(id).then(data => { if (active) { setAsset(data); setStatus(''); } }).catch(() => { if (active) setStatus('No se pudo cargar la vista previa.'); });
        return () => { active = false; };
    }, [id, type]);
    return <aside className={`asset-inspector ${collapsed ? 'is-collapsed' : ''}`} aria-label="Inspector de entidad">
        <header><button aria-label={collapsed ? 'Expandir inspector' : 'Colapsar inspector'} onClick={() => setCollapsed(v => !v)}>{collapsed ? <PanelRightOpen size={18} /> : <PanelRightClose size={18} />}</button>{!collapsed && <><strong>Inspector</strong><button aria-label="Cerrar inspector" onClick={onClose}><X size={18} /></button></>}</header>
        {!collapsed && <div className="inspector-body"><span className="entity-type"><TypeGlyph type={type} /> {type}</span><h3>{asset?.name || label}</h3>
            {status && <p role="status">{status.startsWith('Cargando') && <Loader2 size={14} className="animate-spin" />} {status}</p>}
            {asset && <><p>{asset.mime_type || asset.type}</p>{asset.mime_type?.startsWith('image/') && asset.download_url && <img className="asset-thumbnail" src={asset.download_url} alt={asset.name} />}<div className="asset-tags">{asset.tags?.slice(0, 6).map((tag, i) => <span key={i}>{tag}</span>)}</div><button className="btn-primary" onClick={() => dialog.current?.showModal()}><ExternalLink size={15} /> Open Asset</button></>}
            <details open><summary>Why is this here?</summary>{context.length ? <ul>{context.map((text, i) => <li key={i}>{text}</li>)}</ul> : <p>Seleccionado en la visualización actual. No hay más evidencia contextual disponible.</p>}</details>
            <details><summary>Datos del nodo</summary><pre>{JSON.stringify(metadata, null, 2)}</pre></details>
        </div>}
        <dialog ref={dialog} className="asset-dialog" onClick={e => { if (e.target === dialog.current) dialog.current.close(); }}><header><h2>{asset?.name || label}</h2><button aria-label="Cerrar archivo" onClick={() => dialog.current?.close()}><X size={20} /></button></header>{asset && <AssetViewer asset={asset} />}</dialog>
    </aside>;
}
