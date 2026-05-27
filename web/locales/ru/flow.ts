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
  ui_32c65d8d: '标题',
  ui_392f3dfd: '名称必须字母、数字 или 下划线，并使用下划线分隔多单词',
  ui_fe7509e0: '值',

};
