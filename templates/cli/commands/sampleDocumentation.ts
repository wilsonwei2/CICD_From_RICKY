import { getSampleDataDocumentation } from '../api';
import { setupCommand } from '../utils/setup';

const sampleDocumentation = setupCommand(async (name) => {
  const documentation = await getSampleDataDocumentation(name);
  process.stdout.write(documentation);
});

export default sampleDocumentation;
