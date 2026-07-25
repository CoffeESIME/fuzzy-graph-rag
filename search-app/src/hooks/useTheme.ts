import { useState, useEffect, useCallback } from 'react';

export type Theme = 'dark' | 'light';

const STORAGE_KEY = 'graphrag-theme';

function getSystemTheme(): Theme {
    if (typeof window === 'undefined') return 'dark';
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function applyTheme(theme: Theme) {
    document.documentElement.setAttribute('data-theme', theme);
    if (theme === 'dark') {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
}

/**
 * useTheme — Manages light/dark theme preference.
 * Reads from localStorage, falls back to system preference.
 * Applies `data-theme` attribute to <html> immediately (no flash).
 */
export function useTheme() {
    const [theme, setThemeState] = useState<Theme>(() => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
            if (stored === 'light' || stored === 'dark') return stored;
        } catch {
            // localStorage may be unavailable in some contexts
        }
        return getSystemTheme();
    });

    // Apply on mount and every time theme changes
    useEffect(() => {
        applyTheme(theme);
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch {
            // ignore
        }
    }, [theme]);

    // Also listen for OS-level preference changes
    useEffect(() => {
        const mq = window.matchMedia('(prefers-color-scheme: light)');
        const handler = (e: MediaQueryListEvent) => {
            // Only auto-switch if user hasn't set a manual preference
            try {
                const stored = localStorage.getItem(STORAGE_KEY);
                if (!stored) {
                    setThemeState(e.matches ? 'light' : 'dark');
                }
            } catch {
                setThemeState(e.matches ? 'light' : 'dark');
            }
        };
        mq.addEventListener('change', handler);
        return () => mq.removeEventListener('change', handler);
    }, []);

    const toggleTheme = useCallback(() => {
        setThemeState(prev => (prev === 'dark' ? 'light' : 'dark'));
    }, []);

    const setTheme = useCallback((t: Theme) => {
        setThemeState(t);
    }, []);

    return { theme, toggleTheme, setTheme };
}
