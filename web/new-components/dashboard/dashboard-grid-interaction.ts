import { noCompactor, type Compactor } from 'react-grid-layout/core';

// Moving/resizing one card must not cascade through the rest of the dashboard.
// Preserve the saved coordinates in preview too; "紧凑排列" remains an explicit action.
export const dashboardGridCompactor: Compactor = { ...noCompactor, preventCollision: true };
