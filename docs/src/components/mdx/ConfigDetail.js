import React, { useState, useEffect } from 'react';
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

function NestedTypeTable({ nestedTypes }) {
  if (!nestedTypes || nestedTypes.length === 0) return null;

  return (
    <table className="nested-type-table">
      <thead>
        <tr>
          <th>Type</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
        {nestedTypes.map((type, idx) => (
          <tr key={idx}>
            <td>
              {type.type === 'link' ? (
                <Link to={type.url}>{type.text}</Link>
              ) : (
                type.name || type.type
              )}
            </td>
            <td>{type.description || type.content}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ConfigDetail({ config }) {
  const styles = {
    descriptionSection: {
      marginBottom: '2rem',
    },
    documentationLink: {
      color: 'var(--ifm-color-primary)',
      textDecoration: 'none',
    },
    typeCell: {
      position: 'relative',
    },
    expandButton: {
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      padding: '0 4px',
      color: 'var(--ifm-color-primary)',
      display: 'inline-flex',
      alignItems: 'center',
      marginLeft: '5px'
    },
    nestedTableContainer: {
      marginTop: '8px',
      marginBottom: '4px',
      backgroundColor: 'var(--ifm-table-stripe-background)',
      borderRadius: '4px',
      padding: '8px',
      border: '1px solid var(--ifm-table-border-color)'
    }
  };

  const { name, description, documentationUrl, parameters } = config;

  // Initialize expandedParams state
  const [expandedParams, setExpandedParams] = useState({});

  // Use useEffect to set initial expand state when component mounts
  useEffect(() => {
    const initialExpanded = {};
    parameters.forEach(param => {
      // Auto-expand if nested types count is less than 5
      if (param.nestedTypes && param.nestedTypes.length > 0 && param.nestedTypes.length < 5) {
        initialExpanded[param.name] = true;
      }
    });
    setExpandedParams(initialExpanded);
  }, [parameters]);

  const toggleExpand = (paramName) => {
    setExpandedParams(prev => ({
      ...prev,
      [paramName]: !prev[paramName]
    }));
  };

  return (
    <div>
      {description && (
        <div style={styles.descriptionSection}>
          <p>{description}</p>
          {documentationUrl && (
            <p>
              Details can be found in: <br />
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

      <h2>Parameters</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Required</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {parameters.map((param) => {
            const hasNestedTypes = param.nestedTypes && param.nestedTypes.length > 0;
            const isExpanded = expandedParams[param.name];

            return (
              <tr key={param.name}>
                <td><code>{param.name}</code></td>
                <td style={styles.typeCell}>
                  {param.type}
                  {hasNestedTypes && (
                    <button
                      style={styles.expandButton}
                      onClick={() => toggleExpand(param.name)}
                      aria-label={isExpanded ? "Collapse" : "Expand"}
                      title={isExpanded ? "Collapse" : "Expand"}
                    >
                      {isExpanded ? '▼' : '►'}
                    </button>
                  )}
                  {hasNestedTypes && isExpanded && (
                    <div style={styles.nestedTableContainer}>
                      <NestedTypeTable nestedTypes={param.nestedTypes} />
                    </div>
                  )}
                </td>
                <td>{param.required ? '✅' : '❌'}</td>
                <td>
                  <div>{param.description}</div>
                  {param.validValues && (
                    <div>
                      Valid values:
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
                      Defaults：<CodeValue value={param.defaultValue} />
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <style jsx>{`
        .nested-type-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 0.9em;
        }
        
        .nested-type-table th,
        .nested-type-table td {
          padding: 6px 8px;
          border: 1px solid var(--ifm-table-border-color);
          text-align: left;
        }
        
        .nested-type-table th {
          background-color: var(--ifm-color-emphasis-200);
        }
      `}</style>
    </div>
  );
}