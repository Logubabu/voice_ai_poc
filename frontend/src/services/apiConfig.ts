/**
 * Resolves the backend base URL dynamically from environment variables
 * or defaults to relative path for same-origin / reverse-proxied deployments.
 */
export const getBackendUrl = (): string => {
  const envUrl = import.meta.env.VITE_BACKEND_URL?.trim();
  if (envUrl) {
    return envUrl.replace(/\/$/, '');
  }

  // By default, return empty string for relative paths so requests route
  // through the reverse proxy (Nginx, Vite dev proxy, CloudFront, ALB, etc.)
  // without hardcoding any host, IP, or port.
  return '';
};

export const BACKEND_URL = getBackendUrl();
