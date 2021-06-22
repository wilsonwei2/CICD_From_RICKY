import path from 'path';
import chalk from 'chalk';
import i18next, { TFunction } from 'i18next';
import backend from 'i18next-fs-backend';

let i18nInitialized = false;

const addTranslations = async (text: string, filename: string, locale: string): Promise<string> => {
  const theFile = path.normalize(filename);
  const basename = path.basename(theFile, path.extname(theFile));
  let t: TFunction;

  try {
    if (!i18nInitialized) {
      t = await i18next
        .use(backend)
        .init({
          fallbackLng: 'en_US',
          // ns: [basename],
          // defaultNS: '',
          lng: locale,
          // debug: true,
          backend: {
            loadPath: `${path.resolve(path.dirname(theFile))}/translations-{{lng}}.json`,
          },
        });
      i18nInitialized = true;
    } else {
      t = await i18next.changeLanguage(locale);
    }
  } catch {
    process.stdout.write(chalk.yellow('failed to load translations - skipping'));
    return text;
  }
  return text.replaceAll(/\[{3}(\S*)]{3}/gm, (ignore, key: string) => {
    const isCommon = key.startsWith('#');
    return t(`${isCommon ? 'common' : basename}.${isCommon ? key.substr(1) : key}`);
  });
};

export default addTranslations;
