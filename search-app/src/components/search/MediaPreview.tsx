import { FileText, ExternalLink } from 'lucide-react';

interface MediaPreviewProps {
    path?: string;
    url?: string;
    className?: string;
}

export default function MediaPreview({ path, url, className = '' }: MediaPreviewProps) {
    // Prefer the presigned URL from backend (url), fallback to path if needed (though path alone won't work for private files)
    const mediaSource = url || path;

    if (!mediaSource) return null;

    // Use URL for display, or path/filename for label
    const displayLabel = path ? path.split('/').pop() : 'Archivo';

    // Infer type from extension (using path if available, or url)
    const ext = (path || url || '').split('.').pop()?.split('?')[0].toLowerCase() || '';

    const isImage = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext);
    const isAudio = ['mp3', 'wav', 'ogg', 'm4a', 'flac'].includes(ext);
    const isVideo = ['mp4', 'webm', 'mov'].includes(ext);
    const isPdf = ['pdf'].includes(ext);

    if (isImage) {
        return (
            <div className={`media-preview-image ${className}`} style={{
                marginTop: 10,
                borderRadius: 'var(--radius-sm)',
                overflow: 'hidden',
                border: '1px solid var(--border-subtle)',
                background: 'var(--bg-input)'
            }}>
                <img
                    src={mediaSource}
                    alt="Preview"
                    loading="lazy"
                    style={{
                        width: '100%',
                        height: 'auto',
                        maxHeight: 300,
                        objectFit: 'contain',
                        display: 'block'
                    }}
                />
            </div>
        );
    }

    if (isAudio) {
        return (
            <div className={`media-preview-audio ${className}`} style={{ marginTop: 10 }}>
                <audio controls style={{ width: '100%', height: 40 }}>
                    <source src={mediaSource} />
                    Tu navegador no soporta el elemento de audio.
                </audio>
            </div>
        );
    }

    if (isVideo) {
        return (
            <div className={`media-preview-video ${className}`} style={{ marginTop: 10 }}>
                <video controls style={{ width: '100%', borderRadius: 'var(--radius-sm)', maxHeight: 300 }}>
                    <source src={mediaSource} />
                    Tu navegador no soporta el elemento de video.
                </video>
            </div>
        );
    }

    // Default fallback (File link card)
    return (
        <a
            href={mediaSource}
            target="_blank"
            rel="noopener noreferrer"
            className={`media-preview-file ${className}`}
            style={{
                display: 'flex', alignItems: 'center', gap: 10,
                marginTop: 10, padding: '8px 12px',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                textDecoration: 'none',
                color: 'var(--text-primary)',
                transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--accent-indigo)';
                e.currentTarget.style.background = 'var(--bg-card-hover)';
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-subtle)';
                e.currentTarget.style.background = 'var(--bg-input)';
            }}
        >
            <div style={{
                width: 32, height: 32,
                borderRadius: 4,
                background: 'rgba(99, 102, 241, 0.1)',
                color: 'var(--accent-indigo)',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
                {isPdf ? <FileText size={18} /> : <ExternalLink size={18} />}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: '0.85rem', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {displayLabel}
                </p>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Abrir archivo original
                </p>
            </div>
            <ExternalLink size={14} color="var(--text-muted)" />
        </a>
    );
}
