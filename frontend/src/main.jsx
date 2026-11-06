import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import { registerSW } from './pwa.js';
import './styles.css';

registerSW();
createRoot(document.getElementById('root')).render(<StrictMode><App /></StrictMode>);
