import fs from 'fs';
import path from 'path';
import { promisify } from 'es6-promisify';
import { from, merge, of } from 'rxjs';
import {
  concatMap, delay, map, mergeMap, switchMap,
} from 'rxjs/operators';
import globby from 'globby';
import chalk from 'chalk';
import addTranslations from '../utils/addTranslations';
import { setupCommand } from '../utils/setup';
import { updateTemplate, updateStyle } from '../api';

const readFile = promisify(fs.readFile);

type FileType = 'template' | 'style';

interface FileData {
  content: string;
  file: string;
  basename: string;
  type: FileType;
  locale: string | undefined;
}

const getBasename = (filename: string) => {
  const theFile = path.normalize(filename);
  return path.basename(theFile, path.extname(theFile));
};

const fromFiles = (glob: string, type: FileType) => from(globby(glob)).pipe(
  switchMap((files) => from(files)),
  mergeMap((file: string) => from(readFile(file)).pipe(
    map((buffer) => ({
      content: buffer.toString('utf-8'),
      file,
      basename: getBasename(file),
      type,
    }) as FileData),
  )),
);

const addLocales = (locales: string[]) => switchMap((file: FileData) => from(locales).pipe(
  map((locale) => ({ ...file, locale })),
));

const doTranslations = (skipTranslation: boolean) => concatMap((file: FileData) => (
  skipTranslation || !file.locale
    ? of(file)
    : from(addTranslations(file.content, file.file, file.locale)).pipe(
      map((content) => ({ ...file, content })),
    )
));

const updateAll = setupCommand(async (locales: string[], { skipTranslation }) => {
  await merge(
    fromFiles('*.j2', 'template').pipe(
      addLocales(locales),
      doTranslations(skipTranslation),
    ),
    fromFiles('*.css', 'style'),
  ).pipe(
    concatMap((item) => of(item).pipe(delay(1000 * 5))), // 5 seconds
    switchMap(({
      file, type, basename, locale, content,
    }) => {
      // eslint-disable-next-line no-console, sonarjs/no-nested-template-literals
      console.info(`ìmporting ${type} ${chalk.yellow(file)} ${locale ? `(${chalk.blue(locale)})` : ''}`);
      return type === 'template' && locale
        ? updateTemplate(basename, locale, content) : updateStyle(file, content);
    }),
  ).subscribe();
});

export default updateAll;
