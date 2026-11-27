import { StrictMode, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-sans/700.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import './globals.css';
import App from './App';

const raiz = document.getElementById('root');
if (!raiz) {
    throw new Error('Elemento #root não encontrado.');
}

createRoot(raiz).render(createElement(StrictMode, null, createElement(App)));
