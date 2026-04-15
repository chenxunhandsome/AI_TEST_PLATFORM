import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '')
  const backendTarget = env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000'
  const wsTarget = env.VITE_WS_TARGET || backendTarget.replace(/^http/i, 'ws')
  const devPort = Number.parseInt(env.VITE_DEV_PORT || '3000', 10)
  const devHost = env.VITE_DEV_HOST || '0.0.0.0'

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    css: {
      preprocessorOptions: {
        scss: {
          api: 'modern-compiler',
          silenceDeprecations: ['legacy-js-api'],
        },
      },
    },
    optimizeDeps: {
      esbuildOptions: {
        target: 'es2022',
      },
      force: true,
      exclude: ['tree-sitter'],
    },
    build: {
      target: 'es2022',
    },
    server: {
      port: Number.isNaN(devPort) ? 3000 : devPort,
      host: devHost,
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        Pragma: 'no-cache',
        Expires: '0',
      },
      proxy: {
        '^/api/': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
        },
        '^/media/': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
        },
        '^/app-automation-templates/': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
        },
        '^/app-automation-reports/': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
        },
        '^/ws/': {
          target: wsTarget,
          ws: true,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on('error', () => {})
            proxy.on('proxyReqWs', (proxyReq, req, socket) => {
              socket.on('error', () => {})
            })
          },
        },
      },
    },
    assetsInclude: ['**/*.wasm'],
  }
})
