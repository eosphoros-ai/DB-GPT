import { LoadingOutlined } from '@ant-design/icons';

function MuiLoading({ visible }: { visible: boolean }) {
  if (!visible) return null;

  return (
    <div className="absolute w-full h-full top-0 left-0 flex justify-center items-center z-10 bg-white dark:bg-black bg-opacity-50 dark:bg-opacity-50 backdrop-blur-sm text-3xl animate-fade animate-duration-200">
      <LoadingOutlined />
    </div>
  );
}

export default MuiLoading;
