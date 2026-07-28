import { apiInterceptors, getDocumentList, kbLsJson } from '@/client/api';
import { IDocument, ISpace, KbFileEntry } from '@/types/knowledge';
import { FileOutlined, FileTextOutlined, FolderOpenOutlined, FolderOutlined, LoadingOutlined } from '@ant-design/icons';
import { Tree } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface IProps {
  currentSpaceName: string;
  currentSpace?: ISpace | null;
  onSelectDocument: (doc: IDocument | null) => void;
  onSelectSpace: (space: ISpace) => void;
  onSelectFile?: (file: KbFileEntry | null) => void;
}

type TreeNodeData = DataNode & {
  path?: string;
  isDir?: boolean;
  docId?: number;
  fileData?: KbFileEntry;
};

/**
 * Knowledge Tree sidebar.
 * Shows only the current space's file directory tree.
 * Directories are lazy-loaded when expanded.
 * First level is auto-expanded on load.
 */
export default function KnowledgeTree({ currentSpaceName, onSelectDocument, onSelectFile }: IProps) {
  const { t } = useTranslation();
  const [treeData, setTreeData] = useState<TreeNodeData[]>([]);
  const [loadedKeys, setLoadedKeys] = useState<Set<string>>(new Set());
  const [loadingKeys, setLoadingKeys] = useState<Set<string>>(new Set());
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  const [isFileTree, setIsFileTree] = useState(true); // whether space has file_path metadata

  // Root node key for the space
  const rootKey = `space-${currentSpaceName}`;

  // Load root-level entries on mount
  useEffect(() => {
    if (!currentSpaceName) return;
    (async () => {
      // Try the structured file tree first (kbLsJson)
      const [, data] = await apiInterceptors(kbLsJson(currentSpaceName, { path: '', limit: 500 }));

      if (data && data.entries && data.entries.length > 0) {
        // Space has file_path metadata — build file tree
        setIsFileTree(true);
        const childNodes: TreeNodeData[] = data.entries.map((entry: KbFileEntry) => ({
          key: entry.is_dir ? `dir-${entry.path}` : `file-${entry.path}`,
          title: entry.is_dir ? (
            <span>
              {entry.name} <span className='text-xs text-gray-400'>({entry.child_count})</span>
            </span>
          ) : (
            <span>
              {entry.name} {entry.language && <span className='text-xs text-gray-400 ml-1'>{entry.language}</span>}
            </span>
          ),
          icon: entry.is_dir ? <FolderOutlined /> : <FileOutlined />,
          isLeaf: !entry.is_dir,
          isDir: entry.is_dir,
          path: entry.path,
          docId: entry.doc_id,
          fileData: entry,
        }));

        setTreeData([
          {
            key: rootKey,
            title: currentSpaceName,
            icon: <FolderOpenOutlined />,
            isLeaf: false,
            children: childNodes,
          },
        ]);
        // Auto-expand the root node to show first level
        setExpandedKeys([rootKey]);
        setLoadedKeys(new Set([rootKey]));
      } else {
        // Fallback: no file_path metadata — show document list from getDocumentList
        setIsFileTree(false);
        const [, docData] = await apiInterceptors(getDocumentList(currentSpaceName, { page: 1, page_size: 200 }));
        const docNodes: TreeNodeData[] = (docData?.data || []).map((doc: IDocument) => ({
          key: `doc-${doc.id}`,
          title: doc.doc_name,
          icon: <FileTextOutlined />,
          isLeaf: true,
          isDir: false,
          docId: doc.id,
        }));

        setTreeData([
          {
            key: rootKey,
            title: currentSpaceName,
            icon: <FolderOpenOutlined />,
            isLeaf: false,
            children: docNodes,
          },
        ]);
        setExpandedKeys([rootKey]);
        setLoadedKeys(new Set([rootKey]));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSpaceName]);

  // Lazy-load directory contents on expand
  const handleExpand = async (keys: React.Key[], info: any) => {
    setExpandedKeys(keys as string[]);
    const expandedNode = info.node as TreeNodeData;
    const nodeKey = expandedNode.key as string;

    // Only load if not already loaded and it's a directory node
    if (loadedKeys.has(nodeKey) || loadingKeys.has(nodeKey) || !expandedNode.isDir) {
      return;
    }

    setLoadingKeys(prev => new Set(prev).add(nodeKey));

    const dirPath = expandedNode.path || '';
    const [, data] = await apiInterceptors(kbLsJson(currentSpaceName, { path: dirPath, limit: 500 }));

    const childNodes: TreeNodeData[] = (data?.entries || []).map((entry: KbFileEntry) => ({
      key: entry.is_dir ? `dir-${entry.path}` : `file-${entry.path}`,
      title: entry.is_dir ? (
        <span>
          {entry.name} <span className='text-xs text-gray-400'>({entry.child_count})</span>
        </span>
      ) : (
        <span>
          {entry.name} {entry.language && <span className='text-xs text-gray-400 ml-1'>{entry.language}</span>}
        </span>
      ),
      icon: entry.is_dir ? <FolderOutlined /> : <FileOutlined />,
      isLeaf: !entry.is_dir,
      isDir: entry.is_dir,
      path: entry.path,
      docId: entry.doc_id,
      fileData: entry,
    }));

    setTreeData(prev => updateTreeChildren(prev, nodeKey, childNodes));
    setLoadedKeys(prev => new Set(prev).add(nodeKey));
    setLoadingKeys(prev => {
      const next = new Set(prev);
      next.delete(nodeKey);
      return next;
    });
  };

  const handleSelect = (keys: React.Key[], info: any) => {
    setSelectedKeys(keys as string[]);
    const node = info.node as TreeNodeData;

    if (!isFileTree) {
      // Document list mode — construct IDocument from node
      if (node.docId) {
        onSelectDocument({
          id: node.docId,
          doc_name: (node.title as string) || '',
          doc_type: '',
          content: '',
          chunk_size: 0,
          gmt_created: '',
          gmt_modified: '',
          last_sync: '',
          result: '',
          space: currentSpaceName,
          status: '',
          vector_ids: '',
        });
      }
      onSelectFile?.(null);
      return;
    }

    // File tree mode — when a file is clicked, construct a minimal IDocument
    if (!node.isDir && node.docId) {
      const fileName = node.fileData?.name || (node.title as string) || '';
      onSelectDocument({
        id: node.docId,
        doc_name: fileName,
        doc_type: node.fileData?.file_type || '',
        content: '',
        chunk_size: 0,
        gmt_created: '',
        gmt_modified: '',
        last_sync: '',
        result: '',
        space: currentSpaceName,
        status: '',
        vector_ids: '',
      });
      onSelectFile?.(node.fileData || null);
    } else {
      onSelectFile?.(null);
    }
  };

  return (
    <div className='h-full flex flex-col'>
      <div className='px-3 py-2 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider'>
        {t('Knowledge_Space')}
      </div>
      <div className='flex-1 overflow-auto'>
        <Tree.DirectoryTree
          treeData={treeData}
          expandedKeys={expandedKeys}
          selectedKeys={selectedKeys}
          onExpand={handleExpand}
          onSelect={handleSelect}
          showIcon
          blockNode
          className='knowledge-tree'
          switcherLoadingIcon={<LoadingOutlined />}
        />
      </div>
    </div>
  );
}

/** Recursively update children of a specific node in the tree. */
function updateTreeChildren(tree: TreeNodeData[], targetKey: string, newChildren: TreeNodeData[]): TreeNodeData[] {
  return tree.map(node => {
    if (node.key === targetKey) {
      return { ...node, children: newChildren };
    }
    if (node.children) {
      return { ...node, children: updateTreeChildren(node.children, targetKey, newChildren) };
    }
    return node;
  });
}
