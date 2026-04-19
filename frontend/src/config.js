const configuredApiUrl = process.env.REACT_APP_API_URL?.trim();

const fallbackApiUrl =
  typeof window !== 'undefined' && !['localhost', '127.0.0.1'].includes(window.location.hostname)
    ? window.location.origin
    : 'http://localhost:8000';

const API_URL = (configuredApiUrl || fallbackApiUrl).replace(/\/$/, '');

export default API_URL;
