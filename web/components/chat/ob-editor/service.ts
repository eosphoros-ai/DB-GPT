import type { IModelOptions } from '@oceanbase-odc/monaco-plugin-ob/dist/type';
import { ISession } from '../monaco-editor';

/** Adapt the current SQL session into OB schema/table completion services, returning empty lists without a session. */
export function getModelService(
  { delimiter }: { modelId: string; delimiter: string },
  session?: () => ISession | null,
): IModelOptions {
  return {
    delimiter,
    async getTableList(schemaName?: string) {
      return session?.()?.getTableList(schemaName) || [];
    },
    async getTableColumns(tableName: string, _dbName?: string) {
      return session?.()?.getTableColumns(tableName) || [];
    },
    async getSchemaList() {
      return session?.()?.getSchemaList() || [];
    },
  };
}
