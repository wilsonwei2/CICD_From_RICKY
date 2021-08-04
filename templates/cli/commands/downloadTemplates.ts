import { writeFileSync } from 'fs';
import {
  concatMap, defer, delay, from, of, switchMap,
} from 'rxjs';
import chalk from 'chalk';
import { getTemplate, getTemplates } from '../api';
import { setupCommand } from '../utils/setup';

const downloadTemplates = setupCommand(async (locale) => {
  const templates$ = defer(() => getTemplates()).pipe(
    switchMap((templates) => from(templates)), // convert string array to observable
    concatMap((template) => of(template).pipe(delay(1000 * 5))), // delay 5 seconds
    switchMap((template) => from(getTemplate(template, locale)).pipe(
      switchMap((content) => of({
        template,
        content: typeof content === 'string' ? content : JSON.stringify(content),
      })),
    )),
  );

  await templates$.subscribe(({ template, content }) => {
    console.info(`Write template ${chalk.yellow(template)}`); // eslint-disable-line no-console
    writeFileSync(`${template}.j2`, content);
  });
});

export default downloadTemplates;
