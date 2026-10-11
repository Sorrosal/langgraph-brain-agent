import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './app/styles/globals.css';
import { AppProvider } from './app/providers/AppProvider';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element not found. Ensure index.html has <div id="root">.');
}

createRoot(rootElement).render(
  <StrictMode>
    <AppProvider />
  </StrictMode>,
);
