import fs from 'fs';
import { updateStyle as updateStyleAPI } from '../api';
import { setupCommand } from '../utils/setup';

const updateStyle = setupCommand(async (name, styleFile) => {
  const styleFileContent = fs.readFileSync(styleFile).toString();
  await updateStyleAPI(name, styleFileContent);
});

export default updateStyle;
