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
		API_BASE_URL: process.env.API_BASE_URL || 'https://u158074-879a-d00019a9.westa.seetacloud.com:8443'
	}
}

module.exports = nextConfig
