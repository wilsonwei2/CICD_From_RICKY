export const SettingEnvMapping = {
  tenant: 'TENANT',
  stage: 'STAGE',
};

export const settingOrEnv = (
  setting: string | null | '' | undefined,
  envName: string,
): string | undefined => setting ?? process.env[envName];
