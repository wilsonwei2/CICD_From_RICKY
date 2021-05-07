import fs from 'fs';
import { getSampleData, getTemplate, previewDocument } from '../api';
import addTranslations from '../utils/addTranslations';
import { setupCommand } from '../utils/setup';

const preview = setupCommand(async (name, locale, templateFile, dataFile, { skipTranslation }) => {
  let templateFileContent;
  if (templateFile) {
    templateFileContent = fs.readFileSync(templateFile).toString();
  } else {
    templateFileContent = await getTemplate(name, locale);
  }

  if (!skipTranslation) {
    templateFileContent = await addTranslations(templateFileContent, templateFile ?? `${name}.j2`, locale);
  }

  let theSampleData;
  if (dataFile) {
    theSampleData = JSON.parse(fs.readFileSync(dataFile).toString());
  } else {
    theSampleData = await getSampleData(name);
  }

  const previewResult = await previewDocument(name, locale, templateFileContent, theSampleData);
  process.stdout.write(previewResult);
});

export default preview;
