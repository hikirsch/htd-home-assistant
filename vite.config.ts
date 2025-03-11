import { resolve } from 'path';
import { defineConfig } from 'vite'
import tsconfigPaths from 'vite-tsconfig-paths';

export default defineConfig({
  root: 'src',
  dev: {
    sourcemap: true,
  },
  server: {
    port: 3000,
  },
  build: {
    rollupOptions: {
      input: {
        'config-panel': './src/config-panel/index.ts',
      },
      output: {
        dir: './custom_components/htd/assets',
        entryFileNames: '[name]/index.js',
      },
    }
  },
  plugins: [
    tsconfigPaths(),
  ],
})
