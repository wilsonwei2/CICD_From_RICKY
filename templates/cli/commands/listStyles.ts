import { getStyles } from '../api';
import { CommandAction, setupCommand } from '../utils/setup';

const listStyles: CommandAction = setupCommand(async () => {
  const styles = await getStyles();
  styles.forEach((name) => process.stdout.write(`${name}\n`));
});

export default listStyles;
