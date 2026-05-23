process.title = 'equiquant-ui'

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
	server: {
		port: 8888,
		strictPort: true,
		host: '0.0.0.0',
		proxy: {
			'/api': 'http://127.0.0.1:8000',
		},
	},
	plugins: [
		react(),
		VitePWA({
			registerType: 'autoUpdate',
			includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'mask-icon.svg'],
			manifest: {
				name: 'EquiQuant Dashboard',
				short_name: 'EquiQuant',
				description: 'Quant-focused stock analysis dashboard',
				theme_color: '#ffffff',
				icons: [
					{
						src: 'pwa-192x192.png',
						sizes: '192x192',
						type: 'image/png'
					},
					{
						src: 'pwa-512x512.png',
						sizes: '512x512',
						type: 'image/png'
					}
				]
			}
		})
	],
})
