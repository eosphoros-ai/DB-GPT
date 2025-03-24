import React from 'react';
import Link from '@docusaurus/Link';

export function ConfigClassTable({ classes }) {
  if (!classes || classes.length === 0) {
    return <p>No configuration classes available.</p>;
  }

  return (
    <div className="config-class-table-container">
      <table className="config-class-table">
        <thead>
          <tr>
            <th>Class</th>
            <th>Description</th>
            <th>Documentation</th>
          </tr>
        </thead>
        <tbody>
          {classes.map((cls, index) => (
            <tr key={index}>
              <td><code>{cls.name}</code></td>
              <td>{cls.description}</td>
              <td>
                {cls.link ? (
                  <Link to={cls.link}>View Details</Link>
                ) : (
                  '—'
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <style jsx>{`
        .config-class-table-container {
          margin-bottom: 2rem;
          overflow-x: auto;
        }
        
        .config-class-table {
          width: 100%;
          border-collapse: collapse;
        }
        
        .config-class-table th,
        .config-class-table td {
          padding: 8px 12px;
          text-align: left;
          border: 1px solid var(--ifm-table-border-color);
        }
        
        .config-class-table th {
          background-color: var(--ifm-table-head-background);
        }
        
        .config-class-table tr:nth-child(even) {
          background-color: var(--ifm-table-stripe-background);
        }
      `}</style>
    </div>
  );
}