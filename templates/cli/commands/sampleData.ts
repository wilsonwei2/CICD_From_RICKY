import { getSampleData } from '../api';
import { setupCommand } from '../utils/setup';

const sampleData = setupCommand(async (name) => {
  const sampleDataObj = await getSampleData(name);
  process.stdout.write(JSON.stringify(sampleDataObj as unknown, undefined, 2));
});

export default sampleData;
