import fs from 'fs';
import chalk from 'chalk';
import { setupCommand } from '../utils/setup';
import { updateTemplate as updateTemplateAPI } from '../api';
import addTranslations from '../utils/addTranslations';

const updateTemplate = setupCommand(async (name, locale, file, { skipTranslation }) => {
  let fileContent;
  try {
    fileContent = fs.readFileSync(file).toString();
  } catch {
    process.stderr.write(chalk.red(`Error reading file ${chalk.yellow(file)}\n`));
    process.exit(1);
  }

  if (!skipTranslation) {
    fileContent = await addTranslations(fileContent, file, locale);
  }

  await updateTemplateAPI(name, locale, fileContent);
});

export default updateTemplate;
