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
		API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL ||'http://120.26.193.159:5000'
	},
	trailingSlash: true
}

module.exports = nextConfig
