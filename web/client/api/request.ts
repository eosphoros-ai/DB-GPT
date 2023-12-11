import { AxiosRequestConfig } from 'axios';
import { GET, POST } from '.';
import { DbListResponse, DbSupportTypeResponse, PostDbParams, ChatFeedBackSchema } from '@/types/db';
import { DialogueListResponse, IChatDialogueSchema, NewDialogueParam, SceneResponse, ChatHistoryResponse, FeedBack, IDB } from '@/types/chat';
import { IModelData, StartModelParams, BaseModelParams, SupportModel } from '@/types/model';
import {
  GetEditorSQLRoundRequest,
  GetEditorySqlParams,
  PostEditorChartRunParams,
  PostEditorChartRunResponse,
  PostEditorSQLRunParams,
  PostSQLEditorSubmitParams,
} from '@/types/editor';
import { PostAgentHubUpdateParams, PostAgentQueryParams, PostAgentPluginResponse, PostAgentMyPluginResponse } from '@/types/agent';
import {
  AddKnowledgeParams,
  ArgumentsParams,
  ChunkListParams,
  DocumentParams,
  IArguments,
  IChunkList,
  IDocumentResponse,
  ISpace,
} from '@/types/knowledge';
import { UpdatePromptParams, IPrompt, PromptParams } from '@/types/prompt';

/** App */
export const postScenes = () => {
  return POST<null, Array<SceneResponse>>('/api/v1/chat/dialogue/scenes');
};
export const newDialogue = (data: NewDialogueParam) => {
  return POST<NewDialogueParam, IChatDialogueSchema>('/api/v1/chat/dialogue/new', data);
};

/** Database Page */
export const getDbList = () => {
  return GET<null, DbListResponse>('/api/v1/chat/db/list');
};
export const getDbSupportType = () => {
  return GET<null, DbSupportTypeResponse>('/api/v1/chat/db/support/type');
};
export const postDbDelete = (dbName: string) => {
  return POST(`/api/v1/chat/db/delete?db_name=${dbName}`);
};
export const postDbEdit = (data: PostDbParams) => {
  return POST<PostDbParams, null>('/api/v1/chat/db/edit', data);
};
export const postDbAdd = (data: PostDbParams) => {
  return POST<PostDbParams, null>('/api/v1/chat/db/add', data);
};
export const postDbTestConnect = (data: PostDbParams) => {
  return POST<PostDbParams, null>('/api/v1/chat/db/test/connect', data);
};

/** Chat Page */
export const getDialogueList = () => {
  return GET<null, DialogueListResponse>('/api/v1/chat/dialogue/list');
};
export const getUsableModels = () => {
  return GET<null, Array<string>>('/api/v1/model/types');
};
export const postChatModeParamsList = (chatMode: string) => {
  return POST<null, IDB[]>(`/api/v1/chat/mode/params/list?chat_mode=${chatMode}`);
};
export const postChatModeParamsInfoList = (chatMode: string) => {
  return POST<null, Record<string, string>>(`/api/v1/chat/mode/params/info?chat_mode=${chatMode}`);
};
export const getChatHistory = (convId: string) => {
  return GET<null, ChatHistoryResponse>(`/api/v1/chat/dialogue/messages/history?con_uid=${convId}`);
};
export const postChatModeParamsFileLoad = ({
  convUid,
  chatMode,
  data,
  config,
  model,
}: {
  convUid: string;
  chatMode: string;
  data: FormData;
  model: string;
  config?: Omit<AxiosRequestConfig, 'headers'>;
}) => {
  return POST<FormData, ChatHistoryResponse>(
    `/api/v1/chat/mode/params/file/load?conv_uid=${convUid}&chat_mode=${chatMode}&model_name=${model}`,
    data,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      ...config,
    },
  );
};

/** Menu */
export const delDialogue = (conv_uid: string) => {
  return POST(`/api/v1/chat/dialogue/delete?con_uid=${conv_uid}`);
};

/** Editor */
export const getEditorSqlRounds = (id: string) => {
  return GET<null, GetEditorSQLRoundRequest>(`/api/v1/editor/sql/rounds?con_uid=${id}`);
};
export const postEditorSqlRun = (data: PostEditorSQLRunParams) => {
  return POST<PostEditorSQLRunParams>(`/api/v1/editor/sql/run`, data);
};
export const postEditorChartRun = (data: PostEditorChartRunParams) => {
  return POST<PostEditorChartRunParams, PostEditorChartRunResponse>(`/api/v1/editor/chart/run`, data);
};
export const postSqlEditorSubmit = (data: PostSQLEditorSubmitParams) => {
  return POST<PostSQLEditorSubmitParams>(`/api/v1/sql/editor/submit`, data);
};
export const getEditorSql = (id: string, round: string | number) => {
  return POST<GetEditorySqlParams, string | Array<any>>('/api/v1/editor/sql', { con_uid: id, round });
};

/** knowledge */
export const getArguments = (knowledgeName: string) => {
  return POST<any, IArguments>(`/knowledge/${knowledgeName}/arguments`, {});
};
export const saveArguments = (knowledgeName: string, data: ArgumentsParams) => {
  return POST<ArgumentsParams, IArguments>(`/knowledge/${knowledgeName}/argument/save`, data);
};

export const getSpaceList = () => {
  return POST<any, Array<ISpace>>('/knowledge/space/list', {});
};
export const getDocumentList = (knowLedgeName: string, data: Record<string, number>) => {
  return POST<Record<string, number>, IDocumentResponse>(`/knowledge/${knowLedgeName}/document/list`, data);
};

export const addDocument = (knowledgeName: string, data: DocumentParams) => {
  return POST<DocumentParams, number>(`/knowledge/${knowledgeName}/document/add`, data);
};

export const addSpace = (data: AddKnowledgeParams) => {
  return POST<AddKnowledgeParams, Array<any>>(`/knowledge/space/add`, data);
};

export const syncDocument = (spaceName: string, data: Record<string, Array<number>>) => {
  return POST<Record<string, Array<number>>, string | null>(`/knowledge/${spaceName}/document/sync`, data);
};

export const uploadDocument = (knowLedgeName: string, data: FormData) => {
  return POST<FormData, number>(`/knowledge/${knowLedgeName}/document/upload`, data);
};

export const getChunkList = (spaceName: string, data: ChunkListParams) => {
  return POST<ChunkListParams, IChunkList>(`/knowledge/${spaceName}/chunk/list`, data);
};

export const delDocument = (spaceName: string, data: Record<string, string>) => {
  return POST<Record<string, string>, null>(`/knowledge/${spaceName}/document/delete`, data);
};

export const delSpace = (data: Record<string, string>) => {
  return POST<Record<string, string>, null>(`/knowledge/space/delete`, data);
};

/** models */
export const getModelList = () => {
  return GET<null, Array<IModelData>>('/api/v1/worker/model/list');
};

export const stopModel = (data: BaseModelParams) => {
  return POST<BaseModelParams, boolean>('/api/v1/worker/model/stop', data);
};

export const startModel = (data: StartModelParams) => {
  return POST<StartModelParams, boolean>('/api/v1/worker/model/start', data);
};

export const getSupportModels = () => {
  return GET<null, Array<SupportModel>>('/api/v1/worker/model/params');
};

/** Agent */
export const postAgentQuery = (data: PostAgentQueryParams) => {
  return POST<PostAgentQueryParams, PostAgentPluginResponse>('/api/v1/agent/query', data);
};
export const postAgentHubUpdate = (data?: PostAgentHubUpdateParams) => {
  return POST<PostAgentHubUpdateParams>('/api/v1/agent/hub/update', data ?? { channel: '', url: '', branch: '', authorization: '' });
};
export const postAgentMy = (user?: string) => {
  return POST<undefined, PostAgentMyPluginResponse>('/api/v1/agent/my', undefined, { params: { user } });
};
export const postAgentInstall = (pluginName: string, user?: string) => {
  return POST('/api/v1/agent/install', undefined, { params: { plugin_name: pluginName, user }, timeout: 60000 });
};
export const postAgentUninstall = (pluginName: string, user?: string) => {
  return POST('/api/v1/agent/uninstall', undefined, { params: { plugin_name: pluginName, user }, timeout: 60000 });
};
export const postAgentUpload = (user = '', data: FormData, config?: Omit<AxiosRequestConfig, 'headers'>) => {
  return POST<FormData>('/api/v1/personal/agent/upload', data, {
    params: { user },
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    ...config,
  });
};

/** chat feedback **/
export const getChatFeedBackSelect = () => {
  return GET<null, FeedBack>(`/api/v1/feedback/select`, undefined);
};
export const getChatFeedBackItme = (conv_uid: string, conv_index: number) => {
  return GET<null, Record<string, string>>(`/api/v1/feedback/find?conv_uid=${conv_uid}&conv_index=${conv_index}`, undefined);
};
export const postChatFeedBackForm = ({ data, config }: { data: ChatFeedBackSchema; config?: Omit<AxiosRequestConfig, 'headers'> }) => {
  return POST<ChatFeedBackSchema, any>(`/api/v1/feedback/commit`, data, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...config,
  });
};

/** prompt */
export const getPromptList = (data: PromptParams) => {
  return POST<PromptParams, Array<IPrompt>>('/prompt/list', data);
};

export const updatePrompt = (data: UpdatePromptParams) => {
  return POST<UpdatePromptParams, []>('/prompt/update', data);
};

export const addPrompt = (data: UpdatePromptParams) => {
  return POST<UpdatePromptParams, []>('/prompt/add', data);
};
