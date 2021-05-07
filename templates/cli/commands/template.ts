import { getTemplate } from '../api';
import { setupCommand } from '../utils/setup';

const template = setupCommand(async (name, locale) => {
  const templateContent = await getTemplate(name, locale);
  process.stdout.write(templateContent);
});

export default template;
