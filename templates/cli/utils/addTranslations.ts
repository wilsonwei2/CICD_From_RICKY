import path from 'path';
import chalk from 'chalk';
import i18next, { TFunction } from 'i18next';
import backend from 'i18next-fs-backend';

const addTranslations = async (text: string, filename: string, locale: string): Promise<string> => {
  const theFile = path.normalize(filename);
  const basename = path.basename(theFile, path.extname(theFile));
  let t: TFunction;

  try {
    t = await i18next
      .use(backend)
      .init({
        fallbackLng: 'en_US',
        ns: [basename],
        defaultNS: basename,
        lng: locale,
        backend: {
          loadPath: `${path.dirname(theFile)}/${basename}-{{lng}}.json`,
        },
      });
  } catch {
    process.stdout.write(chalk.yellow('failed to load translations - skipping'));
    return text;
  }
  return text.replaceAll(/\[{3}(\S*)]{3}/gm, (ignore, key) => t(key));
};

export default addTranslations;
