import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Maximize2, Minimize2, FileImage, X } from 'lucide-react';

export type FigurePreset = 'screen' | 'presentation' | 'paper';
export default function VisualizationFrame({ title, children, toolbar, legend, preset = 'screen', onPresetChange, className = '' }: {
    title: string; children: ReactNode; toolbar?: ReactNode; legend?: ReactNode;
    preset?: FigurePreset; onPresetChange?: (preset: FigurePreset) => void; className?: string;
}) {
    const ref = useRef<HTMLElement>(null);
    const [expanded, setExpanded] = useState(false);
    const [figure, setFigure] = useState(false);
    useEffect(() => {
        if (!expanded && !figure) return;
        const previous = document.activeElement as HTMLElement | null;
        const overflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        ref.current?.focus();
        const key = (e: KeyboardEvent) => {
            if (e.key === 'Escape') { setFigure(false); setExpanded(false); }
            if (e.key === 'Tab') {
                const items = Array.from(ref.current?.querySelectorAll<HTMLElement>('button,input,select,[tabindex="0"]') ?? []).filter(el => el.offsetParent !== null);
                const first = items[0], last = items[items.length - 1];
                if (e.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) { e.preventDefault(); last?.focus(); }
                else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
            }
        };
        document.addEventListener('keydown', key);
        return () => { document.body.style.overflow = overflow; document.removeEventListener('keydown', key); previous?.focus(); };
    }, [expanded, figure]);
    return <section ref={ref} tabIndex={-1} aria-label={title} role={expanded || figure ? 'dialog' : undefined} aria-modal={expanded || figure ? true : undefined}
        className={`visualization-frame ${expanded || figure ? 'is-expanded' : ''} ${figure ? 'is-figure' : ''} ${className}`}
        data-preset={preset} data-theme={preset === 'paper' ? 'light' : undefined}>
        <header className="viz-header"><strong>{title}</strong><div className="viz-actions">
            {onPresetChange && <select aria-label="Preset de figura" value={preset} onChange={e => onPresetChange(e.target.value as FigurePreset)}><option value="screen">Screen</option><option value="presentation">Presentation</option><option value="paper">Paper</option></select>}
            <button title="Figure Mode" onClick={() => setFigure(true)}><FileImage size={16} /> Figura</button>
            <button title={expanded ? 'Salir de pantalla completa' : 'Pantalla completa'} aria-label={expanded ? 'Salir de pantalla completa' : 'Pantalla completa'} onClick={() => setExpanded(v => !v)}>{expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}</button>
        </div></header>
        {toolbar && <div className="graph-toolbar">{toolbar}</div>}
        <div className="viz-content">{children}</div>
        {legend}
        {figure && <button className="figure-exit" onClick={() => setFigure(false)}><X size={16} /> Salir de figura · Esc</button>}
    </section>;
}
