/**
 * config.js 模块单元测试
 */

// Mock fetch
global.fetch = jest.fn();

// 在每个测试前重置模块状态
beforeEach(() => {
    jest.resetModules();
    global.fetch.mockClear();
});

describe('config.js', () => {
    describe('buildApiUrl', () => {
        test('should build correct URL with leading slash', async () => {
            const { buildApiUrl } = await import('../../app/frontend/scripts/config.js');
            const url = buildApiUrl('/api/sessions');
            expect(url).toBe('http://127.0.0.1:8000/api/sessions');
        });

        test('should build correct URL without leading slash', async () => {
            const { buildApiUrl } = await import('../../app/frontend/scripts/config.js');
            const url = buildApiUrl('api/sessions');
            expect(url).toBe('http://127.0.0.1:8000/api/sessions');
        });

        test('should handle base URL with trailing slash', async () => {
            const { buildApiUrl } = await import('../../app/frontend/scripts/config.js');
            // Default config has no trailing slash
            const url = buildApiUrl('/api/test');
            expect(url).toBe('http://127.0.0.1:8000/api/test');
        });
    });

    describe('loadConfig', () => {
        test('should use default config when fetch fails', async () => {
            global.fetch.mockRejectedValueOnce(new Error('Network error'));
            
            const { loadConfig, getConfig } = await import('../../app/frontend/scripts/config.js');
            await loadConfig();
            
            const config = getConfig();
            expect(config.apiBaseUrl).toBe('http://127.0.0.1:8000');
        });

        test('should load config from config.json', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ apiBaseUrl: 'http://api.example.com' })
            });
            
            // Need fresh module
            jest.resetModules();
            const { loadConfig, getConfig } = await import('../../app/frontend/scripts/config.js');
            await loadConfig();
            
            const config = getConfig();
            expect(config.apiBaseUrl).toBe('http://api.example.com');
        });

        test('should return cached config on subsequent calls', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ apiBaseUrl: 'http://cached.example.com' })
            });
            
            jest.resetModules();
            const { loadConfig } = await import('../../app/frontend/scripts/config.js');
            
            await loadConfig();
            await loadConfig(); // Second call
            
            // fetch should only be called once
            expect(global.fetch).toHaveBeenCalledTimes(1);
        });
    });

    describe('getApiBaseUrl', () => {
        test('should return default API base URL', async () => {
            const { getApiBaseUrl } = await import('../../app/frontend/scripts/config.js');
            expect(getApiBaseUrl()).toBe('http://127.0.0.1:8000');
        });
    });

    describe('getConfig', () => {
        test('should return a copy of config', async () => {
            const { getConfig } = await import('../../app/frontend/scripts/config.js');
            const config1 = getConfig();
            const config2 = getConfig();
            
            // Should be equal but not same reference
            expect(config1).toEqual(config2);
            expect(config1).not.toBe(config2);
        });
    });
});
