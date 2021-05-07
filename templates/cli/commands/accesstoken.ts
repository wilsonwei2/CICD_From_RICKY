import { setupCommand, CommandAction, accessToken } from '../utils/setup';

const accesstoken: CommandAction = setupCommand(async () => {
  process.stdout.write(accessToken);
});

export default accesstoken;
