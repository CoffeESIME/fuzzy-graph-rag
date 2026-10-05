import { useRef, useState, type ReactNode } from 'react';
import { ZoomIn, ZoomOut, Scan, Download } from 'lucide-react';
import VisualizationFrame, { type FigurePreset } from './VisualizationFrame';
import { downloadFigure } from './figureExport';
import { cssColor } from './visualSystem';

/** Keeps the existing SVG chart renderer; zoom and pan only transform its viewport. */
export default function ChartFrame({ children, title, legend, controls, inspector }: { children: ReactNode; title: string; legend?: ReactNode; controls?: ReactNode; inspector?: ReactNode }) {
    const ref = useRef<HTMLDivElement>(null);
    const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null);
    const [preset, setPreset] = useState<FigurePreset>('screen');
    const [zoom, setZoom] = useState(1), [offset, setOffset] = useState({ x: 0, y: 0 });
    const [labels, setLabels] = useState(true), [pan, setPan] = useState(false), [error, setError] = useState('');
    const exportSvg = async (format: 'svg' | 'png') => {
        const svg = ref.current?.querySelector('svg'); if (!svg || !ref.current) return;
        try {
            const clone = svg.cloneNode(true) as SVGSVGElement;
            const originals = [svg, ...svg.querySelectorAll('*')], copies = [clone, ...clone.querySelectorAll('*')];
            originals.forEach((element, i) => {
                const computed = getComputedStyle(element);
                ['fill','stroke','stroke-width','stroke-dasharray','font-family','font-size','font-weight','opacity','visibility','display'].forEach(property => (copies[i] as SVGElement).style.setProperty(property, computed.getPropertyValue(property)));
            });
            const width = svg.clientWidth, height = svg.clientHeight;
            const ns = 'http://www.w3.org/2000/svg';
            const output = document.createElementNS(ns, 'svg'); output.setAttribute('width', String(width)); output.setAttribute('height', String(height+110)); output.setAttribute('viewBox', `0 0 ${width} ${height+110}`);
            const rect = document.createElementNS(ns, 'rect'); rect.setAttribute('width', '100%'); rect.setAttribute('height', '100%'); rect.setAttribute('fill', cssColor(ref.current, '--background')); output.append(rect);
            const text = document.createElementNS(ns, 'text'); text.setAttribute('x','20'); text.setAttribute('y','28'); text.setAttribute('fill',cssColor(ref.current,'--text-primary')); text.setAttribute('font-family','Segoe UI, sans-serif'); text.setAttribute('font-size','18'); text.textContent = title; output.append(text);
            clone.setAttribute('y','45'); clone.setAttribute('width',String(width)); clone.setAttribute('height',String(height)); output.append(clone);
            const caption = text.cloneNode() as SVGTextElement; caption.setAttribute('y',String(height+78)); caption.setAttribute('font-size','12'); caption.textContent = ref.current.closest('.visualization-frame')?.querySelector('.graph-legend')?.textContent ?? ''; output.append(caption);
            await downloadFigure(new XMLSerializer().serializeToString(output), format, 'observatory-chart'); setError('');
        } catch { setError('No se pudo exportar esta figura.'); }
    };
    return <VisualizationFrame title={title} preset={preset} onPresetChange={setPreset} legend={legend} toolbar={<>
        <button aria-label="Acercar" onClick={() => setZoom(z => Math.min(6,z*1.25))}><ZoomIn size={16}/></button><button aria-label="Alejar" onClick={() => setZoom(z => Math.max(.5,z/1.25))}><ZoomOut size={16}/></button><button onClick={() => { setZoom(1); setOffset({x:0,y:0}); }}><Scan size={16}/> Ajustar</button>
        <label><input type="checkbox" checked={pan} onChange={e => setPan(e.target.checked)}/> Pan</label><label><input type="checkbox" checked={labels} onChange={e => setLabels(e.target.checked)}/> Labels</label>
        {controls}<button onClick={() => exportSvg('svg')}><Download size={16}/> SVG</button><button onClick={() => exportSvg('png')}>PNG ×3</button>{error && <span role="alert">{error}</span>}
    </>}>
        <div ref={ref} className={`chart-stage ${labels ? '' : 'hide-chart-labels'}`} style={{ touchAction: pan ? 'none' : 'auto', cursor: pan ? 'grab' : undefined }}
            onPointerDown={e => { if (!pan) return; drag.current = { x:e.clientX, y:e.clientY, px:offset.x, py:offset.y }; e.currentTarget.setPointerCapture(e.pointerId); }}
            onPointerMove={e => { if (drag.current) setOffset({x:drag.current.px+e.clientX-drag.current.x,y:drag.current.py+e.clientY-drag.current.y}); }}
            onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
            <div style={{ width:'100%', height:'100%', transform:`translate(${offset.x}px,${offset.y}px) scale(${zoom})`, transformOrigin:'center' }}>{children}</div>
        </div>{inspector && <div className="chart-inspector">{inspector}</div>}
    </VisualizationFrame>;
}
