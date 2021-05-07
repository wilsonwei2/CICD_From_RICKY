import prompts from 'prompts';
import chalk from 'chalk';
import setup, { Config } from '../../utils/setup';

const getCredentials = async (initial?: Config) => {
  let cancelled = false;
  let credentials;
  credentials = await prompts([
    {
      type: 'text',
      name: 'tenant',
      message: 'Tenant?',
      validate: (value) => value !== '',
      initial: initial?.tenant,
    },
    {
      type: 'select',
      name: 'stage',
      message: 'Stage?',
      choices: [
        { title: 'Sandbox', value: 'x' },
        { title: 'Staging', value: 's' },
        { title: 'Production', value: 'p' },
      ],
      initial: initial?.stage,
    },
    {
      type: 'text',
      name: 'username',
      message: 'Username?',
      validate: (value) => value !== '',
      initial: initial?.username,
    },
    {
      type: 'password',
      name: 'password',
      message: 'Password?',
      validate: (value) => value !== '',
    },
  ], {
    onCancel: () => {
      cancelled = true;
    },
  });
  if (cancelled) {
    credentials = undefined;
  }
  return credentials;
};

export default async (): Promise<void> => {
  let authenticated = false;
  let credentials;
  while (!authenticated) {
    // eslint-disable-next-line no-await-in-loop
    credentials = await getCredentials(credentials);
    if (!credentials) {
      process.exit(1);
    }
    try {
      // eslint-disable-next-line no-await-in-loop
      await setup(credentials);
      authenticated = true;
    } catch {
      process.stdout.write(chalk.red.bold('❌ Error logging in.\n'));
    }
  }
};
