#!/usr/bin/env node
import { Command } from 'commander';
import packageJson from './package.json';
import {
  interactive, accesstoken,
  list, template, updateTemplate, sampleData, sampleDocumentation, preview,
  listStyles, updateStyle,
} from './commands';

const program = new Command(packageJson.name)
  .version(packageJson.version);

const commonOptions = (cmd: Command): Command => cmd
  .option('-t, --tenant <tenant>', 'Tenant')
  .option('-s, --stage <stage>', 'Stage')
  .option('-u, --username <username>', 'Username')
  .option('-p, --password <password>', 'Password')
  .option('--accesstoken <accesstoken>', 'Access Token');

const main = async () => {
  commonOptions(program
    .command('interactive', {
      isDefault: true,
      hidden: true,
    })
    .description('Interactive mode')
    .action(interactive) as Command);

  commonOptions(program
    .command('accesstoken')
    .description('get access token')
    .action(accesstoken) as Command);

  commonOptions(program
    .command('list')
    .description('List all templates')
    .action(list) as Command);

  commonOptions(program
    .command('template <name> <locale>')
    .description('Get a template')
    .action(template) as Command);

  commonOptions(program
    .command('update-template <name> <locale> <file>')
    .option('--skip-translation', 'Skip the translation process')
    .description('Get a template')
    .action(updateTemplate) as Command);

  commonOptions(program
    .command('sample-data <name> ')
    .description('Get sample data for a template')
    .action(sampleData) as Command);

  commonOptions(program
    .command('sample-documentation <name> ')
    .description('Get sample documentation for a template')
    .action(sampleDocumentation) as Command);

  commonOptions(program
    .command('preview <name> <locale> [template] [data]')
    .option('--skip-translation', 'Skip the translation process')
    .description('Get sample documentation for a template')
    .action(preview) as Command);

  commonOptions(program
    .command('list-styles')
    .description('List all styles')
    .action(listStyles) as Command);

  commonOptions(program
    .command('update-style <style> <file>')
    .description('Update a style')
    .action(updateStyle) as Command);

  await program.parseAsync(process.argv);
};

main();
