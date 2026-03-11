/**
 * Configuration Management Module
 * Responsible for loading and providing runtime configuration
 */

const DEFAULT_CONFIG = {
    apiBaseUrl: 'http://127.0.0.1:8000'
};

let config = { ...DEFAULT_CONFIG };
let configLoaded = false;

/**
 * Load runtime configuration
 * @returns {Promise<object>} Configuration object
 */
export async function loadConfig() {
    if (configLoaded) {
        return config;
    }
    
    try {
        const response = await fetch('/config.json');
        if (response.ok) {
            const loaded = await response.json();
            config = { ...DEFAULT_CONFIG, ...loaded };
            console.log('[Config] Loaded:', config);
        }
    } catch (e) {
        console.warn('[Config] Using default config:', e.message);
    }
    
    configLoaded = true;
    return config;
}

/**
 * Get current configuration
 * @returns {object} Configuration object
 */
export function getConfig() {
    return { ...config };
}

/**
 * Get API base URL
 * @returns {string} API base URL
 */
export function getApiBaseUrl() {
    return config.apiBaseUrl;
}

/**
 * Build full API URL
 * @param {string} path - API path
 * @returns {string} Full URL
 */
export function buildApiUrl(path) {
    const base = config.apiBaseUrl.replace(/\/$/, '');
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    return `${base}${cleanPath}`;
}

export default {
    loadConfig,
    getConfig,
    getApiBaseUrl,
    buildApiUrl
};
