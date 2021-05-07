import { setupCommand, CommandAction } from '../utils/setup';
import { getTemplates } from '../api';

const list: CommandAction = setupCommand(async () => {
  const templates = await getTemplates();
  templates.forEach((name) => process.stdout.write(`${name}\n`));
});

export default list;
