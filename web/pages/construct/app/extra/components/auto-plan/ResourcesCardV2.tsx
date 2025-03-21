import MyEmpty from '@/components/common/MyEmpty';
import { IResource } from '@/types/app';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Popconfirm, Select, Typography } from 'antd';
import classNames from 'classnames';
import { concat } from 'lodash';
import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { v4 as uuid } from 'uuid';
import { resourceTypeIcon } from '../../config';
import ResourceContentV2 from './ResourceContentV2';

interface ResourceTabProps extends IResource {
  uid?: string;
  icon?: string;
  initVal?: any;
  name?: string;
}

const ResourcesCardV2: React.FC<{
  name: string;
  updateData: (data: any) => void;
  initValue?: any;
  resourceTypeOptions: Record<string, any>[];
}> = ({ name, updateData, resourceTypeOptions, initValue }) => {
  const { t } = useTranslation();
  const resources = useRef<ResourceTabProps[]>(initValue || []);
  const [curIcon, setCurIcon] = useState<{ uid: string; icon: string }>({
    uid: '',
    icon: '',
  });

  // Track the last update to avoid circular updates
  const lastUpdateRef = useRef<string>('');

  // Initialize resource tabs
  const [resourcesTabs, setResourcesTabs] = useState<ResourceTabProps[]>(
    initValue?.map((item: any) => {
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

  // Delete resource
  const remove = (e: React.MouseEvent, item: ResourceTabProps) => {
    e?.stopPropagation();
    const findActiveIndex = resourcesTabs.findIndex(i => i.uid === activeKey);
    const filteredResources = resourcesTabs?.filter(i => i.uid !== item.uid);
    resources.current = resources.current.filter(i => i.uid !== item.uid) || [];

    // Send the updated resource data to the parent component
    const newData = [name, resources.current];
    const newUpdateStr = JSON.stringify(newData);
    if (newUpdateStr !== lastUpdateRef.current) {
      lastUpdateRef.current = newUpdateStr;
      updateData(newData);
    }

    setResourcesTabs(filteredResources);

    // Handle the selected tab after deletion
    if (item.uid === activeKey) {
      if (findActiveIndex === resourcesTabs.length - 1 && findActiveIndex !== 0) {
        // If the last tab is deleted, select the new last tab
        setActiveKey(filteredResources?.[filteredResources.length - 1]?.uid || '');
      } else {
        // Otherwise, select the same position or the previous tab
        const newActiveIndex = Math.min(findActiveIndex, filteredResources.length - 1);
        setActiveKey(filteredResources?.[newActiveIndex]?.uid || '');
      }
    }
  };

  const addSource = () => {
    const uid = uuid();
    const defaultResourceType = resourceTypeOptions?.filter(item => item.value !== 'all')?.[0]?.value || '';
    const newResource = {
      is_dynamic: false,
      type: defaultResourceType,
      value: '',
      uid,
      name: t('resource') + ` ${resources.current.length + 1}`,
    };

    resources.current = concat(resources.current, [newResource]);

    // Send the updated resource data to the parent component
    const newData = [name, resources.current];
    const newUpdateStr = JSON.stringify(newData);
    if (newUpdateStr !== lastUpdateRef.current) {
      lastUpdateRef.current = newUpdateStr;
      updateData(newData);
    }

    setResourcesTabs(prev => [
      ...prev,
      {
        icon: defaultResourceType,
        type: defaultResourceType,
        uid,
        initVal: newResource,
        name: t('resource') + ` ${prev.length + 1}`,
      },
    ]);

    setActiveKey(uid);
    setCurIcon({
      uid,
      icon: defaultResourceType,
    });
  };

  // Update the icon of the resource tab
  useEffect(() => {
    if (curIcon.uid && curIcon.icon) {
      setResourcesTabs(
        resourcesTabs.map(item => {
          if (curIcon?.uid === item.uid) {
            return {
              ...item,
              icon: curIcon.icon,
              type: curIcon.icon,
            };
          }
          return item;
        }),
      );
    }
  }, [curIcon]);

  // Update the filtered resource tabs
  useEffect(() => {
    setFilterResourcesTabs([...resourcesTabs]);
  }, [resourcesTabs]);

  return (
    <div className='flex flex-1 px-3 py-4 border border-[#d6d8da] rounded-md' style={{ minHeight: '450px' }}>
      {/* Resource list on the left */}
      <div className='flex flex-col w-40 h-full'>
        {/* Resource type filter */}
        <Select
          options={resourceTypeOptions}
          className='w-full h-8'
          variant='borderless'
          defaultValue='all'
          onChange={(value: string) => {
            if (value === 'all') {
              setFilterResourcesTabs(resourcesTabs);
              setActiveKey(resourcesTabs?.[0]?.uid || '');
            } else {
              const newSourcesTabs = resourcesTabs?.filter(item => item?.icon === value);
              setActiveKey(newSourcesTabs?.[0]?.uid || '');
              setFilterResourcesTabs(newSourcesTabs);
            }
          }}
        />

        {/* Resource tab list */}
        <div className='flex flex-1 flex-col gap-1 overflow-y-auto'>
          {filterResourcesTabs?.map(item => (
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
              {/* Resource type icon */}
              {resourceTypeIcon[item.icon || '']}

              {/* Resource name (editable) */}
              <Typography.Text
                className={classNames('flex flex-1 items-center text-sm p-0 m-0 mx-2 line-clamp-1', {
                  'text-[#0c75fc]': item.uid === activeKey,
                })}
                editable={{
                  autoSize: {
                    maxRows: 1,
                  },
                  onChange: v => {
                    // Update the resource name
                    const updatedTabs = resourcesTabs.map(i => {
                      if (i.uid === item.uid) {
                        return {
                          ...i,
                          name: v,
                        };
                      }
                      return i;
                    });
                    setResourcesTabs(updatedTabs);

                    // Update the resource data
                    resources.current = resources.current.map(i => {
                      if (i.uid === item.uid) {
                        return {
                          ...i,
                          name: v,
                        };
                      }
                      return i;
                    });

                    // Send the updated resource data to the parent component
                    const newData = [name, resources.current];
                    const newUpdateStr = JSON.stringify(newData);
                    if (newUpdateStr !== lastUpdateRef.current) {
                      lastUpdateRef.current = newUpdateStr;
                      updateData(newData);
                    }
                  },
                }}
                ellipsis={{
                  tooltip: true,
                }}
              >
                {item.name}
              </Typography.Text>

              {/* Delete resource button (displayed on hover) */}
              <Popconfirm
                title={t('want_delete')}
                onConfirm={e => {
                  remove(e, item);
                }}
                onCancel={e => e?.stopPropagation()}
              >
                <DeleteOutlined
                  className={`text-sm cursor-pointer absolute right-2 ${hoverKey === item.uid ? 'opacity-100' : 'opacity-0'}`}
                  style={{ top: '50%', transform: 'translateY(-50%)' }}
                  onClick={e => e.stopPropagation()}
                />
              </Popconfirm>
            </div>
          ))}
        </div>

        {/* Add resource button */}
        <Button className='w-full h-8' type='dashed' block icon={<PlusOutlined />} onClick={addSource}>
          {t('add_resource')}
        </Button>
      </div>

      {/* Resource configuration on the right */}

      <div className='flex flex-1 ml-6' style={{ minHeight: '430px', overflowY: 'auto' }}>
        {filterResourcesTabs && filterResourcesTabs?.length > 0 ? (
          <div className='flex flex-1'>
            {filterResourcesTabs?.map(item => (
              <ResourceContentV2
                key={item.uid}
                classNames={item.uid === activeKey ? 'block' : 'hidden'}
                initValue={item.initVal}
                resourceType={item.icon || ''}
                resourceTypeOptions={resourceTypeOptions}
                setCurIcon={setCurIcon}
                updateData={(data: any) => {
                  // Update the resource data
                  resources.current = resources.current?.map(i => {
                    if (i?.uid === data?.uid) {
                      return {
                        ...i,
                        ...data,
                      };
                    }
                    return i;
                  });

                  // Send the updated resource data to the parent component
                  const newData = [name, resources.current];
                  const newUpdateStr = JSON.stringify(newData);
                  if (newUpdateStr !== lastUpdateRef.current) {
                    lastUpdateRef.current = newUpdateStr;
                    updateData(newData);
                  }
                }}
                uid={item.uid || ''}
              />
            ))}
          </div>
        ) : (
          <MyEmpty className='w-40 h-40' />
        )}
      </div>
    </div>
  );
};

export default ResourcesCardV2;
