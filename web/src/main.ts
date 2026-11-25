import { StrictMode, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App';

const raiz = document.getElementById('root');
if (!raiz) {
    throw new Error('Elemento #root não encontrado.');
}

createRoot(raiz).render(createElement(StrictMode, null, createElement(App)));
