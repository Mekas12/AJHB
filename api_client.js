// API Client para AJHB - Reemplaza IndexedDB con backend
const API_CONFIG = {
    baseURL: window.location.origin + '/api',
    timeout: 30000,
    maxRetries: 3,
    retryDelay: 1000
};

class APIClient {
    constructor(config = API_CONFIG) {
        this.baseURL = config.baseURL;
        this.timeout = config.timeout;
        this.maxRetries = config.maxRetries;
        this.retryDelay = config.retryDelay;
    }

    async request(method, endpoint, data = null, retryCount = 0) {
        const url = `${this.baseURL}${endpoint}`;
        
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' },
            signal: AbortSignal.timeout(this.timeout)
        };

        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            
            if (!response.ok) {
                if (response.status === 503 && retryCount < this.maxRetries) {
                    await this.sleep(this.retryDelay * (retryCount + 1));
                    return this.request(method, endpoint, data, retryCount + 1);
                }
                const error = await response.json().catch(() => ({ error: 'Error desconocido' }));
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            return await response.json();

        } catch (error) {
            if (error.name === 'AbortError' || error.message.includes('fetch')) {
                if (retryCount < this.maxRetries) {
                    console.warn(`Reintento ${retryCount + 1}/${this.maxRetries} para ${method} ${endpoint}`);
                    await this.sleep(this.retryDelay * (retryCount + 1));
                    return this.request(method, endpoint, data, retryCount + 1);
                }
                throw new Error('No se pudo conectar con el servidor');
            }
            throw error;
        }
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async getAll(tabla) {
        return this.request('GET', `/${tabla}`);
    }

    async getOne(tabla, id) {
        return this.request('GET', `/${tabla}/${id}`);
    }

    async add(tabla, data) {
        const result = await this.request('POST', `/${tabla}`, data);
        return result.id;
    }

    async put(tabla, id, data) {
        await this.request('PUT', `/${tabla}/${id}`, data);
        return true;
    }

    async delete(tabla, id) {
        await this.request('DELETE', `/${tabla}/${id}`);
        return true;
    }

    async getStats() {
        return this.request('GET', '/stats/dashboard');
    }

    async healthCheck() {
        return this.request('GET', '/health');
    }
}

const api = new APIClient();

// Interfaz compatible con IndexedDB
const DB = {
    async getAll(tabla) {
        try {
            return await api.getAll(tabla);
        } catch (error) {
            console.error(`Error obteniendo ${tabla}:`, error);
            mostrarToast(`Error al cargar ${tabla}`, 'error');
            return [];
        }
    },

    async get(tabla, id) {
        try {
            return await api.getOne(tabla, id);
        } catch (error) {
            console.error(`Error obteniendo ${tabla}/${id}:`, error);
            return null;
        }
    },

    async add(tabla, data) {
        try {
            return await api.add(tabla, data);
        } catch (error) {
            console.error(`Error creando en ${tabla}:`, error);
            mostrarToast(`Error al guardar en ${tabla}`, 'error');
            throw error;
        }
    },

    async put(tabla, id, data) {
        try {
            await api.put(tabla, id, data);
            return true;
        } catch (error) {
            console.error(`Error actualizando ${tabla}/${id}:`, error);
            mostrarToast(`Error al actualizar ${tabla}`, 'error');
            throw error;
        }
    },

    async delete(tabla, id) {
        try {
            await api.delete(tabla, id);
            return true;
        } catch (error) {
            console.error(`Error eliminando ${tabla}/${id}:`, error);
            mostrarToast(`Error al eliminar de ${tabla}`, 'error');
            throw error;
        }
    },

    async getStats() {
        try {
            return await api.getStats();
        } catch (error) {
            console.error('Error obteniendo estadísticas:', error);
            return {
                totalClientes: 0,
                totalAsientos: 0,
                totalActivos: 0,
                cuentasCobrar: 0,
                cuentasPagar: 0,
                saldoBancos: 0
            };
        }
    },

    async inicializarCatalogoCuentas() {
        try {
            await api.request('POST', '/cuentas/inicializar');
            return true;
        } catch (error) {
            console.error('Error inicializando catálogo:', error);
            return false;
        }
    }
};

// Verificar conexión al cargar
window.addEventListener('load', async () => {
    try {
        await api.healthCheck();
        console.log('✅ Conectado al backend AJHB');
    } catch (error) {
        console.error('❌ No se pudo conectar al backend:', error);
        mostrarToast('No se pudo conectar al servidor. Verifica que el backend esté ejecutándose en http://localhost:5000', 'error', 'Error de Conexión');
    }
});

console.log('🚀 API Client inicializado');
