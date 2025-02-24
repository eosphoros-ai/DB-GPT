import React from 'react';
import Link from '@docusaurus/Link';

function CodeValue({ value }) {
  if (!value) return null;
  
  if (value.includes('\n') || value.length > 50) {
    return (
      <pre>
        <code>{value}</code>
      </pre>
    );
  }
  
  return <code>{value}</code>;
}

export function ConfigDetail({ config }) {
  const styles = {
    descriptionSection: {
      marginBottom: '2rem',
    },
    documentationLink: {
      color: 'var(--ifm-color-primary)',
      textDecoration: 'none',
    }
  };

  const { name, description, documentationUrl, parameters } = config;

  return (
    <div>
      {description && (
        <div style={styles.descriptionSection}>
          <p>{description}</p>
          {documentationUrl && (
            <p>
              详细文档请参考：
              <Link
                to={documentationUrl}
                style={styles.documentationLink}
                target="_blank"
                rel="noopener noreferrer"
              >
                {documentationUrl}
              </Link>
            </p>
          )}
        </div>
      )}

      <h2>参数列表</h2>
      <table>
        <thead>
          <tr>
            <th>参数名</th>
            <th>类型</th>
            <th>必填</th>
            <th>描述</th>
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
                    有效值：
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
                    默认值：<CodeValue value={param.defaultValue} />
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