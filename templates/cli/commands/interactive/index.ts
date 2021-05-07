import { CommandAction } from '../../utils/setup';
import authConfig from './authConfig';

const interactive: CommandAction = async (): Promise<void> => {
  await authConfig();
};

export default interactive;
