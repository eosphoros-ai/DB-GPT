import { Empty } from 'antd';
import classNames from 'classnames';

interface Props {
  className?: string;
  imgUrl?: string;
}

const MyEmpty: React.FC<Props> = ({ className, imgUrl = '/pictures/empty.png' }) => {
  return (
    <div className={classNames('m-auto', { className })}>
      <Empty image={imgUrl} imageStyle={{ margin: '0 auto', width: '100%', height: '100%' }} />
    </div>
  );
};

export default MyEmpty;
