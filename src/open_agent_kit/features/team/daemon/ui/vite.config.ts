import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const sharedDir = path.resolve(__dirname, "../../../../ui/shared")

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // Resolve bare imports from shared UI files using this app's node_modules.
    // Shared UI lives outside the project root, so Rollup can't find deps
    // via normal node_modules resolution.
    {
      name: 'resolve-shared-deps',
      enforce: 'pre',
      resolveId(source, importer) {
        // Only intercept bare imports from files in the shared UI directory
        if (importer && importer.startsWith(sharedDir) && !source.startsWith('.') && !source.startsWith('/') && !source.startsWith('@oak/ui')) {
          // Let Vite resolve from this project's root
          return this.resolve(source, path.resolve(__dirname, 'src', '_virtual.ts'), { skipSelf: true });
        }
        return null;
      },
    },
  ],
  base: '/static/',
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@oak/ui": sharedDir,
    },
    dedupe: ["react", "react-dom", "@tanstack/react-query", "react-router-dom"],
  },
  server: {
    fs: {
      allow: [
        path.resolve(__dirname, "."),
        sharedDir,
      ],
    },
  },
})
