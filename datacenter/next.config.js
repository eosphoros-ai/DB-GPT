/** @type {import('next').NextConfig} */
const nextConfig = {
	experimental: {
		esmExternals: 'loose'
	},
    images: {
        unoptimized: true
    },
}

module.exports = nextConfig
