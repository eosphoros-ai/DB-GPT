import MyEmpty from '@/new-components/common/MyEmpty';
import { IResource } from '@/types/app';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Popconfirm, Select, Space, Typography } from 'antd';
import classNames from 'classnames';
import { concat } from 'lodash';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { v4 as uuid } from 'uuid';

import { resourceTypeIcon } from '../../config';
import ResourceContent from './ResourceContent';
import { useTranslation } from 'react-i18next';

interface ResourceTabProps extends IResource {
  uid?: string;
  icon?: string;
  initVal?: any;
  name?: string;
}

const ResourcesCard: React.FC<{ name: string; updateData: (data: any) => void; initValue?: any; resourceTypeOptions: Record<string, any>[] }> = ({
  name,
  updateData,
  resourceTypeOptions,
  initValue,
}) => {
  const { t } = useTranslation();
  const resources = useRef<ResourceTabProps[]>(initValue || []);
  const [curIcon, setCurIcon] = useState<{ uid: string; icon: string }>({ uid: '', icon: '' });
  const [resourcesTabs, setResourcesTabs] = useState<ResourceTabProps[]>(
    initValue?.map((item: any, index: number) => {
      return {
        ...item,
        icon: item.type,
        initVal: item,
      };
    }) || [],
  );
  const [filterResourcesTabs, setFilterResourcesTabs] = useState<ResourceTabProps[]>([...resourcesTabs]);
  const [activeKey, setActiveKey] = useState<string>(resourcesTabs?.[0]?.uid || '');
  const [hoverKey, setHoverKey] = useState<string>('');

  // 删除资源
  const remove = (e: any, item: any) => {
    e?.stopPropagation();
    const findActiveIndex = resources.current?.findIndex((i) => i.uid === activeKey);
    const filteredResources = resourcesTabs?.filter((i) => i.uid !== item.uid);
    resources.current = resources.current.filter((i) => i.uid !== item.uid) || [];
    updateData([name, resources.current]);
    setResourcesTabs(filteredResources);
    if (findActiveIndex === resourcesTabs?.length - 1 && findActiveIndex !== 0) {
      setTimeout(() => {
        setActiveKey(filteredResources?.[filteredResources.length - 1]?.uid || '');
      }, 0);
    }
    setActiveKey(filteredResources?.[findActiveIndex]?.uid || '');
  };

  // 添加资源
  const addSource = () => {
    const uid = uuid();
    resources.current = concat(
      resources.current,
      [
        {
          is_dynamic: false,
          type: resourceTypeOptions?.filter((item) => item.value !== 'all')?.[0].value,
          value: '',
          uid,
          name: t('resource') + ` ${resources.current.length + 1}`,
        },
      ].filter(Boolean),
    );
    updateData([name, resources.current]);
    setResourcesTabs((prev: any) => {
      return [
        ...prev,
        {
          icon: resourceTypeOptions?.filter((item) => item.value !== 'all')?.[0]?.value || '',
          uid,
          initVal: {
            is_dynamic: false,
            type: resourceTypeOptions?.filter((item) => item.value !== 'all')?.[0].value,
            value: '',
            uid,
            name: t('resource') + ` ${prev.length + 1}`,
          },
          name: t('resource') + ` ${prev.length + 1}`,
        },
      ];
    });
    setActiveKey(uid);
    setCurIcon({
      uid,
      icon: resourceTypeOptions?.filter((item) => item.value !== 'all')?.[0].value,
    });
  };

  useEffect(() => {
    setFilterResourcesTabs([...resourcesTabs]);
  }, [resourcesTabs]);

  // 资源切换图标同步切换
  useEffect(() => {
    setResourcesTabs(
      resourcesTabs.map((item) => {
        if (curIcon?.uid === item.uid) {
          return {
            ...item,
            icon: curIcon.icon,
          };
        }
        return item;
      }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [curIcon]);

  return (
    <div className="flex flex-1  h-64 px-3 py-4 border border-[#d6d8da] rounded-md">
      <div className="flex flex-col w-40 h-full">
        <Select
          options={resourceTypeOptions}
          className="w-full h-8"
          variant="borderless"
          defaultValue="all"
          onChange={(value: any) => {
            if (value === 'all') {
              setFilterResourcesTabs(resourcesTabs);
              setActiveKey(resourcesTabs?.[0]?.uid || '');
            } else {
              const newSourcesTabs = resourcesTabs?.filter((item) => item?.icon === value);
              setActiveKey(newSourcesTabs?.[0]?.uid || '');
              setFilterResourcesTabs(newSourcesTabs as any);
            }
          }}
        />
        <div className="flex flex-1 flex-col gap-1 overflow-y-auto">
          {filterResourcesTabs?.map((item) => (
            <div
              className={classNames(
                'flex h-8 items-center px-3 pl-[0.6rem] rounded-md hover:bg-[#f5faff] hover:dark:bg-[#606264] cursor-pointer relative',
                {
                  'bg-[#f5faff] dark:bg-[#606264]': item.uid === activeKey,
                },
              )}
              key={item.uid}
              onClick={() => {
                setActiveKey(item.uid || '');
              }}
              onMouseEnter={() => {
                setHoverKey(item.uid || '');
              }}
              onMouseLeave={() => {
                setHoverKey('');
              }}
            >
              {resourceTypeIcon[item.icon || '']}
              <Typography.Text
                className={classNames('flex flex-1 items-center text-sm p-0 m-0 mx-2 line-clamp-1', {
                  'text-[#0c75fc]': item.uid === activeKey,
                })}
                editable={{
                  autoSize: {
                    maxRows: 1,
                  },
                  onChange: (v) => {
                    setResourcesTabs(
                      resourcesTabs.map((i) => {
                        if (i.uid === item.uid) {
                          return {
                            ...i,
                            name: v,
                          };
                        }
                        return i;
                      }),
                    );
                    resources.current = resources.current.map((i) => {
                      if (i.uid === item.uid) {
                        return {
                          ...i,
                          name: v,
                        };
                      }
                      return i;
                    });
                    updateData([name, resources.current]);
                  },
                }}
                ellipsis={{
                  tooltip: true,
                }}
              >
                {item.name}
              </Typography.Text>
              <Popconfirm
                title={t('want_delete')}
                onConfirm={(e) => {
                  remove(e, item);
                }}
                onCancel={(e) => e?.stopPropagation()}
              >
                <DeleteOutlined
                  className={`text-sm cursor-pointer  absolute right-2 ${hoverKey === item.uid ? 'opacity-100' : 'opacity-0'}`}
                  style={{ top: '50%', transform: 'translateY(-50%)' }}
                  onClick={(e) => e.stopPropagation()}
                />
              </Popconfirm>
            </div>
          ))}
        </div>
        <Button className="w-full h-8" type="dashed" block icon={<PlusOutlined />} onClick={addSource}>
          {t('add_resource')}
        </Button>
      </div>
      <div className="flex flex-1 ml-6 ">
        {filterResourcesTabs && filterResourcesTabs?.length > 0 ? (
          <div className="flex flex-1">
            {filterResourcesTabs?.map((item) => (
              <ResourceContent
                key={item.uid}
                classNames={item.uid === activeKey ? 'block' : 'hidden'}
                resourceTypeOptions={resourceTypeOptions}
                initValue={item.initVal}
                setCurIcon={setCurIcon}
                updateData={(data: any) => {
                  resources.current = resources.current?.map((i) => {
                    if (i?.uid === data?.uid) {
                      return {
                        ...i,
                        ...data,
                      };
                    }
                    return i;
                  });
                  updateData([name, resources.current]);
                }}
                uid={item.uid || ''}
              />
            ))}
          </div>
        ) : (
          <MyEmpty className="w-40 h-40" />
        )}
      </div>
    </div>
  );
};
export default ResourcesCard;
