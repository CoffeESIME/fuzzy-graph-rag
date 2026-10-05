import { useEffect, useState, type RefObject } from 'react';
/** Resolve CSS tokens for Canvas/WebGL, which cannot consume CSS var() strings. */
export function useCanvasTheme(ref: RefObject<HTMLElement | null>) {
    const [colors, setColors] = useState({ background: '#10161e', text: '#e9edf1', edge: '#91a5b8' });
    useEffect(() => {
        const read = () => {
            const style = getComputedStyle(ref.current ?? document.documentElement);
            const next = { background: style.getPropertyValue('--background').trim(), text: style.getPropertyValue('--text-primary').trim(), edge: style.getPropertyValue('--graph-edge').trim() };
            setColors(previous => JSON.stringify(previous) === JSON.stringify(next) ? previous : next);
        };
        read(); const observer = new MutationObserver(read);
        observer.observe(document.documentElement, { attributes: true, subtree: true, attributeFilter: ['data-theme', 'data-preset'] });
        return () => observer.disconnect();
    }, [ref]);
    return colors;
}
