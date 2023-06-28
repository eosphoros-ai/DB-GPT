"use client"
import { useRequest } from 'ahooks';
import { sendGetRequest } from '@/utils/request';
import useAgentChat from '@/hooks/useAgentChat';
import ChatBoxComp from '@/components/chatBox';

const AgentPage = (props) => {
	const { data: historyList } = useRequest(async () => await sendGetRequest('/v1/chat/dialogue/messages/history', {
		con_uid: props.params?.agentId
	}), {
		ready: !!props.params?.agentId
	});

	const { handleChatSubmit, history } = useAgentChat({
		queryAgentURL: `/v1/chat/completions`,
			queryBody: {}
	});

	return (
		<div className='mx-auto flex h-full max-w-3xl flex-col gap-6 px-5 pt-6 sm:gap-8 xl:max-w-4xl'>
			<ChatBoxComp messages={historyList?.data || []} onSubmit={handleChatSubmit}/>
		</div>
	)
}
export default AgentPage;