import prompts from 'prompts';

export default async (): Promise<void> => {
  await prompts({
    type: 'select',
    name: 'action',

  });
};
