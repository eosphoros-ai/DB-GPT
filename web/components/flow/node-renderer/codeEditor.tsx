import React, { useState } from 'react';  
import { UnControlled as CodeMirror } from 'react-codemirror2';  

  
export const RenderCodeEditor = ()=> {  
  const [code, setCode] = useState('// 输入你的代码');  
  
  const handleChange = (editor, data, value) => {  
    // 处理代码变化  
    setCode(value);  
  };  
  
  return (  
    <CodeMirror  
      value={code}  
      onChange={handleChange}  
      options={{  
        mode: 'javascript', // 设置语言模式  
        theme: 'material', // 设置主题  
        lineNumbers: true, // 显示行号  
        // 其他配置...  
      }}  
    />  
  );  
}  
  


