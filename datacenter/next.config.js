/** @type {import('next').NextConfig} */
const nextConfig = {
	output: 'export',
	experimental: {
		esmExternals: 'loose'
	},
	typescript: {
		ignoreBuildErrors: true
	},
	env: {
		API_BASE_URL: process.env.API_BASE_URL || 'http://127.0.0.1:5000'
	}
}

module.exports = nextConfig
