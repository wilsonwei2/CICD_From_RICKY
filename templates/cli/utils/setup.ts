import axios from 'axios';
import jwt from 'jsonwebtoken';
import { auth } from '../api';

export const SettingEnvMapping = {
  tenant: 'TENANT',
  stage: 'STAGE',
  username: 'NS_USER',
  password: 'NS_PASSWORD',
  accesstoken: 'NS_ACCESS_TOKEN',
};

export interface Config {
  tenant: string;
  stage: string;
  username?: string;
  password?: string;
  accesstoken?: string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type CommandAction = (...args: any[]) => Promise<void>;

// eslint-disable-next-line import/no-mutable-exports
export let accessToken: string;

const setup = async ({
  tenant, stage,
  username, password, accesstoken,
}: Config): Promise<void> => {
  axios.defaults.baseURL = `https://${tenant}.${stage}.newstore.net`;

  accessToken = accesstoken ?? await auth(username as string, password as string);
  axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
};

const ensureSettingPresentDontEnforce = (
  name: keyof typeof SettingEnvMapping,
  setting: string | undefined, dontEnforce = false,
): string | undefined => {
  let result = setting;
  if (!result) result = process.env[SettingEnvMapping[name]];
  if (!result && !dontEnforce) {
    process.stderr.write(`Missing ${name}\n`);
    process.exit(1);
  }
  return result;
};
const ensureSettingPresent = (
  name: keyof typeof SettingEnvMapping,
  setting: string | undefined,
): string => ensureSettingPresentDontEnforce(name, setting) as string;

export const setupCommand = (fn: CommandAction): CommandAction => async (...args) => {
  let {
    tenant, stage, username, password, accesstoken,
  } = args[args.length - 2];

  tenant = ensureSettingPresent('tenant', tenant);
  stage = ensureSettingPresent('stage', stage);

  if (!accesstoken) accesstoken = ensureSettingPresentDontEnforce('accesstoken', accesstoken, true);
  if (accesstoken) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const decoded = jwt.decode(accesstoken) as Record<string, any>;
    if (!decoded || decoded.exp < Date.now() / 1000) {
      process.stderr.write('access token is expired\n');
      process.exit(1);
    }
  } else {
    username = ensureSettingPresent('username', username);
    password = ensureSettingPresent('password', password);
  }

  await setup({
    tenant,
    stage,
    username: !accesstoken ? username : undefined,
    password: !accesstoken ? password : undefined,
    accesstoken,
  });
  await fn(...args);
};

export default setup;
