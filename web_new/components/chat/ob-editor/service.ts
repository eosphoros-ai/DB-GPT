import type { IModelOptions } from '@oceanbase-odc/monaco-plugin-ob/dist/type';
import { ISession } from '../monaco-editor';


export function getModelService(
  { modelId, delimiter }: { modelId: string; delimiter: string },
  session?: () => ISession | null
): IModelOptions {
  return {
    delimiter,
    async getTableList(schemaName?: string) {
      return session?.()?.getTableList(schemaName) || []
    },
    async getTableColumns(tableName: string, dbName?: string) {
    return session?.()?.getTableColumns(tableName) || []
    },
    async getSchemaList() {
      return session?.()?.getSchemaList() || []
    },
  };
}
