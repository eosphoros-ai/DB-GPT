import { apiInterceptors, getResourceV2 } from '@/client/api';
import ConfigurableForm from '@/components/common/configurable-form';
import { ConfigurableParams } from '@/types/common';
import { Form, Select, Spin, Switch } from 'antd';
import cls from 'classnames';
import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface ResourceContentV2Props {
  uid: string;
  initValue: any;
  updateData: (data: any) => void;
  classNames?: string;
  resourceType: string;
  resourceTypeOptions: Record<string, any>[];
  setCurIcon: React.Dispatch<
    React.SetStateAction<{
      uid: string;
      icon: string;
    }>
  >;
}

/**
 * Parse a resource value field which might be a string or object
 */
const parseResourceValue = (value: any): Record<string, any> => {
  if (!value) return {};

  if (typeof value === 'string') {
    try {
      // Parse the JSON string
      const parsed = JSON.parse(value);

      // Process any complex values that might be serialized
      const result: Record<string, any> = {};

      // Handle each field in the parsed object
      Object.keys(parsed).forEach(key => {
        const fieldValue = parsed[key];

        // Check if the field value is an object with a 'key' property (complex select value)
        if (fieldValue && typeof fieldValue === 'object' && fieldValue !== null && 'key' in fieldValue) {
          // Store just the key value for select fields
          result[key] = fieldValue.key;
        } else {
          // Keep the value as is for other fields
          result[key] = fieldValue;
        }
      });

      return result;
    } catch (e) {
      // If it's not valid JSON, return empty object
      console.error('Failed to parse resource value:', e);
      return {};
    }
  }

  if (typeof value === 'object') {
    // If it's already an object, ensure complex select values are properly processed
    const result: Record<string, any> = {};

    Object.keys(value).forEach(key => {
      const fieldValue = value[key];

      // Check if the field value is an object with a 'key' property (complex select value)
      if (fieldValue && typeof fieldValue === 'object' && fieldValue !== null && 'key' in fieldValue) {
        // Store just the key value for select fields
        result[key] = fieldValue.key;
      } else {
        // Keep the value as is for other fields
        result[key] = fieldValue;
      }
    });

    return result;
  }

  return {};
};

const ResourceContentV2: React.FC<ResourceContentV2Props> = ({
  uid,
  initValue,
  updateData,
  classNames,
  resourceType,
  resourceTypeOptions,
  setCurIcon,
}) => {
  const [form] = Form.useForm();
  const isDynamic = Form.useWatch('is_dynamic', form);
  const selectedType = Form.useWatch('resource_type', form);
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [configParams, setConfigParams] = useState<ConfigurableParams[] | null>(null);

  // Use ref to prevent multiple unnecessary updates
  const updateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastUpdateValueRef = useRef<string>('');
  const isInitializedRef = useRef<boolean>(false);

  // Filter out the "all" option
  const filteredResourceOptions = resourceTypeOptions.filter(option => option.value !== 'all');

  // Handle resource type change
  const handleTypeChange = (value: string) => {
    if (value !== selectedType) {
      // Clear previous configuration parameters
      form.resetFields(['is_dynamic']);

      // Reset the icon to the new type
      setCurIcon({ uid, icon: value });

      // Load the new type's configuration parameters
      fetchResourceParams(value);

      // Force an update after type change
      setTimeout(() => {
        updateResourceData(true);
      }, 800); // Make sure the form is updated before triggering the update
    }
  };

  // Function to get resource configuration parameters using v2 API
  const fetchResourceParams = async (type: string) => {
    setLoading(true);
    try {
      const [err, res] = await apiInterceptors(getResourceV2({ type }));

      if (!err && res) {
        setConfigParams(res);

        // Set default value for the resource type
        if (res.length > 0) {
          // Reset the form content, keeping the resource type
          const currentType = form.getFieldValue('resource_type');
          const isDynamicValue = form.getFieldValue('is_dynamic');
          form.resetFields();
          form.setFieldsValue({
            resource_type: currentType || type,
            is_dynamic: isDynamicValue || false,
          });
        }
      } else {
        setConfigParams(null);
        console.error('Failed to fetch resource params:', err);
      }
    } catch (error) {
      console.error('Error fetching resource params:', error);
      setConfigParams(null);
    } finally {
      setLoading(false);

      // Make sure to trigger an update after parameters are loaded, even if using default values
      if (type === selectedType || !selectedType) {
        setTimeout(() => {
          updateResourceData(true);
        }, 500);
      }
    }
  };
  // Create a new useEffect to listen for changes in configParams
  useEffect(() => {
    // This will trigger an update when the configuration parameters change
    if (configParams && isInitializedRef.current && selectedType) {
      setTimeout(() => {
        updateResourceData(true);
      }, 300);
    }
  }, [configParams, selectedType]);
  // Re-fetch parameters when initial resource type changes or on initialization
  useEffect(() => {
    if (resourceType) {
      // Set initial form values for resource type
      form.setFieldsValue({
        resource_type: resourceType,
      });

      // Fetch parameters for this resource type
      fetchResourceParams(resourceType);

      // Set icon
      setCurIcon({ uid, icon: resourceType });
    }
  }, [resourceType, uid, setCurIcon]);

  // Set initial values when params are loaded and initValue is available
  useEffect(() => {
    if (configParams && initValue && !isInitializedRef.current) {
      try {
        // Parse the value field (could be string or object)
        const valueObj = parseResourceValue(initValue.value);

        // Do not trigger validation, set form values directly
        form.setFields(
          Object.entries({
            resource_type: resourceType,
            is_dynamic: initValue.is_dynamic,
            ...valueObj,
          }).map(([name, value]) => ({
            name,
            value,
            touched: false, // Mark as untouched to avoid validation
            validating: false,
          })),
        );

        // console.log('Set default value:', {
        //   resource_type: resourceType,
        //   is_dynamic: initValue.is_dynamic,
        //   ...valueObj,
        // });

        // Mark as initialized to avoid re-setting values
        isInitializedRef.current = true;

        // Trigger an update after initialization
        setTimeout(() => {
          updateResourceData(true);
        }, 500);
      } catch (error) {
        console.error('Error setting initial values:', error);
      }
    }
  }, [configParams, initValue, form, resourceType]);
  // Update resource data with a debounce
  const updateResourceData = (force = false) => {
    // Clear any existing timeout
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
      updateTimeoutRef.current = null;
    }

    // Lazy update to avoid frequent calls
    updateTimeoutRef.current = setTimeout(() => {
      const rawValues = form.getFieldsValue();
      const currentType = rawValues.resource_type;

      // If no type is selected, do not update
      if (!currentType) return;

      // Handle complex values for select fields
      const processedValues = { ...rawValues };
      if (configParams) {
        configParams.forEach(param => {
          if (
            param.valid_values &&
            Array.isArray(param.valid_values) &&
            param.valid_values.length > 0 &&
            typeof param.valid_values[0] === 'object'
          ) {
            // If the field is present in the form values, make sure we only use the key
            if (processedValues[param.param_name]) {
              const selectedKey = processedValues[param.param_name];
              // Don't convert if it's already a string
              if (typeof selectedKey !== 'string') {
                processedValues[param.param_name] = selectedKey.key || selectedKey;
              }
            }
          }
        });
      }

      // Split the resource type field from the configuration values
      const { resource_type, is_dynamic, ...configOnlyValues } = processedValues;
      // Save even if the object is empty to keep the current state
      const value = isDynamic ? '' : JSON.stringify(configOnlyValues);

      // console.log('Updating resource data with:', {
      //   type: currentType,
      //   is_dynamic: !!isDynamic,
      //   value,
      // });

      // Compare the new value with the last value to avoid unnecessary updates
      const newUpdateValue = JSON.stringify({
        type: currentType,
        is_dynamic: !!isDynamic,
        value,
      });

      if (force || newUpdateValue !== lastUpdateValueRef.current) {
        lastUpdateValueRef.current = newUpdateValue;

        updateData({
          uid,
          type: currentType,
          is_dynamic: !!isDynamic,
          value,
          name: initValue?.name || t('resource'),
        });
      }
    }, 300); // 300ms debounce
  };

  // Handle form values change and validate
  const handleFormValuesChange = (changedValues: any) => {
    // Handle resource type change separately
    if ('resource_type' in changedValues) {
      handleTypeChange(changedValues.resource_type);
      return;
    }

    // Trigger an immediate update if the dynamic type is toggled
    if ('is_dynamic' in changedValues) {
      // Do not validate, update directly
      updateResourceData(true);
      return;
    }

    // Update the form values without validation
    /*     console.log('Form values changed:', changedValues);
    console.log('Form values:', form.getFieldsValue()); */

    const changedFields = Object.keys(changedValues);

    if (changedFields.length > 0) {
      // Just validate the changed fields
      form
        .validateFields(changedFields)
        .then(() => {
          console.log('Field validation success');
          updateResourceData();
        })
        .catch(err => {
          // Ensure the data is updated even if validation fails
          console.log('Field validation error, but still updating:', err);
          updateResourceData();
        });
    } else {
      // If no fields are changed, update directly
      updateResourceData();
    }
  };

  return (
    <div className={cls('flex flex-1', classNames)}>
      <Spin spinning={loading}>
        <Form
          style={{ width: '100%' }}
          form={form}
          labelCol={{ span: 7 }}
          initialValues={{
            resource_type: resourceType,
            is_dynamic: initValue?.is_dynamic || false,
          }}
          onValuesChange={handleFormValuesChange}
        >
          {/* Resource Type */}
          <Form.Item
            label={t('resource_type')}
            name='resource_type'
            rules={[{ required: true, message: t('please_select_resource_type') }]}
          >
            <Select options={filteredResourceOptions} placeholder={t('please_select_resource_type')} />
          </Form.Item>

          {/* Data Dynamic Toggle */}
          <Form.Item label={t('resource_dynamic')} name='is_dynamic' valuePropName='checked'>
            <Switch style={{ background: isDynamic ? '#1677ff' : '#ccc' }} />
          </Form.Item>

          {/* Only show the configuration form if it's not dynamic and the parameters are loaded */}
          {!isDynamic && configParams && <ConfigurableForm params={configParams} form={form} />}
        </Form>
      </Spin>
    </div>
  );
};

export default ResourceContentV2;
