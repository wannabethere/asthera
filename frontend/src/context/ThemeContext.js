import { createContext, useContext, useEffect, useState } from 'react';

const ThemeContext = createContext();

export const ThemeChangeProvider = ({ children }) => {
    const [rawTheme, setRawTheme] = useState(localStorage.getItem('theme') || 'system');
    const [appTheme, setAppTheme] = useState(() => {
        const stored = localStorage.getItem('theme') || 'system';
        if (stored === 'system') {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            return prefersDark ? 'dark' : 'light';
        }
        return stored;
    });

    const handleThemeChange = (selectedTheme) => {
        setRawTheme(selectedTheme);
        localStorage.setItem('theme', selectedTheme);

        if (selectedTheme === 'system') {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            setAppTheme(prefersDark ? 'dark' : 'light');
        } else {
            setAppTheme(selectedTheme);
        }
    };

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', appTheme);
        const rootElement = document.getElementById('root');
        if (rootElement) {
            rootElement.classList.remove('light', 'dark');
            rootElement.classList.add(appTheme);
        }
    }, [appTheme]);

    return (
        <ThemeContext.Provider value={{ appTheme, rawTheme, handleThemeChange }}>
            {children}
        </ThemeContext.Provider>
    );
};

export const useTheme = () => {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};