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
		API_BASE_URL: process.env.API_BASE_URL || 'http://30.183.154.76:5000'
	}
}

module.exports = nextConfig
