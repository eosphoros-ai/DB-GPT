import { FlowEn } from '../en/flow';

type I18nKeys = keyof typeof FlowEn;

interface Resources {
  translation: Record<I18nKeys, string>;
}

export const FlowRu: Resources['translation'] = {
  Upload_Data_Successfully: 'Файл загружен',
  Upload_Data_Failed: 'Ошибка загрузки файла',
  Upload_Data: 'Загрузить данные',
  Code_Editor: 'Редактор кода',
  Open_Code_Editor: 'Открыть редактор кода',
  Export_Flow_Success: 'Поток успешно экспортирован',
  Import_Flow_Success: 'Поток успешно импортирован',
  Import: 'Импорт',
  Export: 'Экспорт',
  Import_Flow: 'Импорт потока',
  Export_Flow: 'Экспорт потока',
  Select_File: 'Выбор файла',
  Save_After_Import: 'Сохранить после импорта',
  Export_File_Type: 'Тип экспорта',
  Export_File_Format: 'Формат экспорта',
  Yes: 'Да',
  No: 'Нет',
  Please_Add_Nodes_First: 'Сначала добавьте узлы',
  Add_Global_Variable_of_Flow: 'Добавить глобальную переменную потока',
  Add_Parameter: 'Добавить параметр',
  Higher_Order_Nodes: 'Узлы высшего порядка',
  All_Nodes: 'Все',
  Import_From_Template: 'Импорт из шаблона',
  Template_Description: 'Описание',
  Template_Name: 'Имя шаблона',
  Template_Label: 'Метка',
  Template_Action: 'Действие',
  minimum_dynamic_fields_warning: 'Оставьте хотя бы одно динамическое поле',

  // phase2 i18n
  title: 'Заголовок',
  name_must_use_letters_numbers_or_underscores_sep:
    'Имя: только буквы, цифры и подчёркивания (слова разделяйте _)',
  value: 'Значение',
  flow_parameter_index_name: 'Имя параметра {{index}}',
  missing_parameter_name: 'Введите имя параметра',
  missing_parameter_label: 'Введите метку параметра',
  missing_parameter_type: 'Выберите тип параметра',
  missing_parameter_value: 'Введите значение параметра',
  flow_parameter_name_placeholder: 'Имя параметра',
  flow_parameter_label_placeholder: 'Метка параметра',
  flow_parameter_description_placeholder: 'Описание параметра',
};
