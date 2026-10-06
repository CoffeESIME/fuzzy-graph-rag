import type { Node, Edge } from 'reactflow';
import { edgeVisual, nodeColors, shapeFor, visualNode } from './visualSystem';

const escape = (text: unknown) => String(text).replace(/[<>&"']/g, char => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' })[char]!);
export function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function downloadFigure(svg: string, format: 'svg' | 'png', filename: string) {
    const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
    if (format === 'svg') return downloadBlob(blob, `${filename}.svg`);
    const url = URL.createObjectURL(blob);
    try {
        const image = new Image();
        await new Promise<void>((resolve, reject) => { image.onload = () => resolve(); image.onerror = () => reject(new Error('No se pudo convertir la figura a PNG.')); image.src = url; });
        const scale = Math.min(3, 8192 / Math.max(image.width, image.height));
        const canvas = document.createElement('canvas'); canvas.width = image.width * scale; canvas.height = image.height * scale;
        const context = canvas.getContext('2d'); if (!context) throw new Error('Canvas no disponible');
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const png = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('PNG no disponible')), 'image/png'));
        downloadBlob(png, `${filename}.png`);
    } finally { URL.revokeObjectURL(url); }
}
export function graphSvg(nodes: Node[], edges: Edge[], options: { title: string; labels: boolean; weights: boolean; background: string; surface: string; text: string; line: string; transparent?: boolean; large?: boolean }) {
    if (!nodes.length) throw new Error('No hay nodos para exportar');
    const minX = Math.min(...nodes.map(n => n.position.x)), minY = Math.min(...nodes.map(n => n.position.y));
    const width = Math.max(760, Math.max(...nodes.map(n => n.position.x + 200)) - minX + 100);
    const graphHeight = Math.max(...nodes.map(n => n.position.y + 76)) - minY + 100;
    const types = [...new Set(nodes.map(n => visualNode(n).type))];
    const kinds = [...new Set(edges.map(e => edgeVisual(e).kind))];
    const entries = [...types, ...kinds.map(k => k === 'normal' ? 'Relación' : k === 'fuzzy' ? 'Fuzzy' : 'Serendipity')];
    const height = graphHeight + 95 + Math.ceil(entries.length / 4) * 28;
    const point = (n: Node) => ({ x: n.position.x - minX + 50, y: n.position.y - minY + 85 });
    const glyph = (type: string, x: number, y: number) => shapeFor(type) === 'circle' ? `<circle cx="${x}" cy="${y}" r="6"/>` : shapeFor(type) === 'diamond' ? `<path d="M${x} ${y-7}l7 7-7 7-7-7Z"/>` : `<rect x="${x-6}" y="${y-6}" width="12" height="12"/>`;
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img"><title>${escape(options.title)}</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 10 5 0 10Z" fill="${options.line}"/></marker></defs>${options.transparent ? '' : `<rect width="100%" height="100%" fill="${options.background}"/>`}<g font-family="Segoe UI, sans-serif" fill="${options.text}"><text x="50" y="35" font-size="20" font-weight="600">${escape(options.title)}</text>
    ${edges.map(e => {
        const a = nodes.find(n => n.id === e.source), b = nodes.find(n => n.id === e.target); if (!a || !b) return '';
        const s = point(a), t = point(b), v = edgeVisual(e);
        const vertical = Math.abs(t.y - s.y) > Math.abs(t.x - s.x);
        const x1 = s.x + (vertical ? 100 : t.x >= s.x ? 200 : 0), y1 = s.y + (vertical ? t.y >= s.y ? 76 : 0 : 38);
        const x2 = t.x + (vertical ? 100 : t.x >= s.x ? 0 : 200), y2 = t.y + (vertical ? t.y >= s.y ? 0 : 76 : 38);
        const label = [options.labels ? e.data?.routeLabel : '', options.labels ? v.relation : '', options.weights && v.weight !== undefined ? String(v.weight) : ''].filter(Boolean).join(' · ');
        return `<path d="M${x1} ${y1}L${x2} ${y2}" fill="none" stroke="${options.line}" stroke-width="${1.5 + Math.max(0, Math.min(1, v.weight ?? .5)) * 2}" ${v.dash ? `stroke-dasharray="${v.dash}"` : ''} ${e.markerEnd ? 'marker-end="url(#arrow)"' : ''}/>${label ? `<text x="${(x1+x2)/2}" y="${(y1+y2)/2-9}" text-anchor="middle" font-size="12" paint-order="stroke" stroke="${options.background}" stroke-width="4" stroke-linejoin="round">${escape(label)}</text>` : ''}`;
    }).join('')}
    ${nodes.map(n => { const p = point(n), v = visualNode(n), color = nodeColors[v.type] ?? '#78818c';
        const words = v.label.match(/.{1,25}(?:\s|$)|.{1,25}/g) ?? [v.label];
        return `<g><title>${escape(v.label)}</title><rect x="${p.x}" y="${p.y}" width="200" height="76" rx="6" fill="${options.surface}" stroke="${color}" stroke-width="${n.selected ? 4 : 2}"/><g fill="none" stroke="${color}" stroke-width="2">${glyph(v.type, p.x+16, p.y+19)}</g><text x="${p.x+30}" y="${p.y+23}" font-size="11">${escape(v.type)}${n.data.role ? ' · ' + escape(n.data.role) : ''}</text>${options.labels ? words.slice(0,2).map((word,i) => `<text x="${p.x+12}" y="${p.y+45+i*17}" font-size="${options.large ? 15 : 14}" font-weight="600">${escape(word.trim())}${i === 1 && words.length > 2 ? '…' : ''}</text>`).join('') : ''}</g>`;
    }).join('')}
    ${entries.map((entry,i) => { const x = 50 + (i%4) * ((width-100)/4), y = graphHeight+55+Math.floor(i/4)*28; return `<g transform="translate(${x} ${y})">${i < types.length ? `<g stroke="${nodeColors[entry] ?? '#888'}" fill="none" stroke-width="2">${glyph(entry, 7, -4)}</g>` : `<path d="M0 -4H20" stroke="${options.line}" stroke-width="2" stroke-dasharray="${entry === 'Fuzzy' ? '7 4' : entry === 'Serendipity' ? '2 5' : ''}"/>`}<text x="26" font-size="12">${escape(entry)}</text></g>`; }).join('')}
    ${options.weights && edges.some(e => edgeVisual(e).weight !== undefined) ? `<text x="50" y="${height-12}" font-size="12">Peso: valor numérico; grosor proporcional (0–1).</text>` : ''}</g></svg>`;
}
