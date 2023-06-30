"use client"
import dynamic from 'next/dynamic'

const DynamicWrapper = dynamic(() => import ('@/components/agentPage'), {
  loading: () => <p>Loading...</p>,
  ssr: false,
});

const DynamicAgentPage = (props: any) => {
	return (
		<div>
			<DynamicWrapper {...props} />
		</div>
	)
}
export default DynamicAgentPage;