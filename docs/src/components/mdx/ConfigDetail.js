import React from 'react';
import Link from '@docusaurus/Link';

// The component that displays code and default values
function CodeValue({ value }) {
  if (!value) return null;
  // 如果是多行或很长的内容，使用代码块
  // If it is multi-line or very long content, use code block
  if (value.includes('\n') || value.length > 50) {
    return (
      <pre>
        <code>{value}</code>
      </pre>
    );
  }

  // Otherwise, use inline code
  return <code>{value}</code>;
}

export function ConfigDetail({ config }) {
  const { name, description, parameters } = config;

  return (
    <div>
      {description && <p>{description}</p>}

      <h2>Parameters</h2>
      <table>
        <thead>
          <tr>
            <th>Parameter Name</th>
            <th>Type</th>
            <th>Required</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {parameters.map((param) => (
            <tr key={param.name}>
              <td><code>{param.name}</code></td>
              <td>
                {param.type}
                {param.nestedTypes && param.nestedTypes.length > 0 && (
                  <span>
                    {' ('}
                    {param.nestedTypes.map((type, idx) => (
                      <React.Fragment key={idx}>
                        {idx > 0 && ', '}
                        {type.type === 'link' ? (
                          <Link to={type.url}>{type.text}</Link>
                        ) : (
                          type.content
                        )}
                      </React.Fragment>
                    ))}
                    {')'}
                  </span>
                )}
              </td>
              <td>{param.required ? '✅' : '❌'}</td>
              <td>
                <div>{param.description}</div>
                {param.validValues && (
                  <div>
                    Available values:
                    {param.validValues.map((value, idx) => (
                      <React.Fragment key={idx}>
                        {idx > 0 && ', '}
                        <CodeValue value={value} />
                      </React.Fragment>
                    ))}
                  </div>
                )}
                {param.defaultValue && (
                  <div>
                    Default Value: <CodeValue value={param.defaultValue} />
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}