import React, { useEffect } from 'react';

import cuid from 'cuid';

const useVisitorId = () => {
  const [visitorId, setVisitorId] = React.useState('');

  useEffect(() => {
    (async () => {
      if (typeof window !== 'undefined') {
        let id = localStorage.getItem('visitorId');

        if (!id) {
          id = cuid();
          localStorage.setItem('visitorId', id);
        }

        setVisitorId(id);
      }
    })();
  }, []);

  return {
    visitorId,
  };
};

export default useVisitorId;
