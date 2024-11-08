import { useSearchParams } from 'next/navigation';

const Libro: React.FC = () => {
  const searchParams = useSearchParams();
  const id = searchParams?.get('id') || '';

  return (
    <>
      <iframe src={`http://localhost:5671/dbgpt?flow_uid=${id}`} className='h-full'></iframe>
    </>
  );
};

export default Libro;
