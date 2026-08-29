import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import Icons from 'unplugin-icons/vite'

/* Same shape as pacos-fontend's, deliberately: Bee asked for one way of doing
 * things across both systems so there is one thing to learn and one thing to
 * check (27-08-2026, "để dễ kiểm soát"). The differences are two, and both are
 * facts about this app rather than choices:
 *
 *   - the API it proxies to is the Python one on 8100, because that service
 *     holds the desktop program's OWN formula files and this app must print
 *     the same numbers the .exe prints;
 *   - the build lands in dist/ and is served by that same service, so the
 *     .exe's update path on this host is not touched.
 */
export default defineConfig({
  plugins: [
    react(),
    // Icons compiled in at BUILD time: nothing calls a CDN while the app runs,
    // so the workshop losing its internet does not lose its icons.
    Icons({ compiler: 'jsx', jsx: 'react', autoInstall: false }),
  ],
  // Must mirror "paths" in tsconfig.json. TypeScript resolves the alias for
  // type checking; Vite has to be told separately for the bundle.
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5174,
    /* The Python API is the single source of truth for every calculation - it
     * imports the .exe's own calculator.py rather than holding a second copy of
     * any formula (LAW P1). The dev server proxies to it; in production the
     * same service serves this build, so the addresses are identical either
     * way and nothing here needs to know which it is. */
    proxy: {
      '/api': { target: 'http://127.0.0.1:8100', changeOrigin: false },
    },
  },
  test: {
    setupFiles: ['./src/test-setup.ts'],
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) return 'vendor'
        },
      },
    },
  },
})
