/** @type {import('next').NextConfig} */
const nextConfig = {
	output: 'export',
	experimental: {
		esmExternals: 'loose'
	},
	typescript: {
		ignoreBuildErrors: true
	}
}

module.exports = nextConfig
