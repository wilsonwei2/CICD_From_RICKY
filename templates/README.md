# Templates

Contains the templates for emails/receipts/... for the project. See `data/` folder.

## CLI tool

Since the templates and styles are maintained using a REST API it's sometimes a bit complicated to handle these assets. So here is a CLI tool to make things a bit easier.

### Build CLI tool

The CLI tool is located in the `cli/` folder. The prequesties are:

- Node.JS 12+
- Yarn

Execute

```
$ yarn
```

To install all dependencies and build the tool.

### Needed environment

The tool needs the following settings:

- Tenant
- Stage
- Credentials or Access Token

Options can be used to provide these settings

```
  -t, --tenant <tenant>        Tenant
  -s, --stage <stage>          Stage
  -u, --username <username>    Username
  -p, --password <password>    Password
  --accesstoken <accesstoken>  Access Token
```

When an access token is provided the settings username and password aren't needed.

Also environment variables can be used to provide these settings:

- `TENANT`
- `STAGE`
- `NS_USER`
- `NS_PASSWORD`
- `ACCESSTOKEN`

Same here - when access token is provided there is no need to provide username/password.

### `accesstoken` - Generate access token

```
$ newstore-templates accesstoken [options]
```

Generates an access token using given username/password and prints it to `stdout`.

### `list` - List all templates

```
$ newstore-templates list [options]
```

List all available templates.

### `update-template` - Update a template for the given locale

```
$ newstore-templates update-template [options]
```

Updates a template for the given locale. Additionally translations will be added for the locale.

Example:

```
$ newstore-templates update-template sales_receipt en_US sales_receipt.j2
```

To skip translation the  `--skip-translation` option can be used.

### `update-all` - Update all templates and styles

```
$ newstore-templates update-all [options] <locales..>
```

This command updates all templates and styles provided in the current working directory. The command looks for `.j2` and `.css` files. The locales needs to be listed as parameters. Also translations will be added.

```
$ newstore-templates update-all en_US fr_CA
```

To skip translation the  `--skip-translation` option can be used.

### `download-templates` - Download all templates

```
$ newstore-templates download-templates [options] <locale>
```

Download all templates for a locale and store it as `.j2` files.

```
$ newstore-templates download-templates en_US
```

### `sample-data` - Output sample data for the given template

```
$ newstore-templates sample-data [options] <name>
```

Output sample data for the given template.

### `sample-documentation` - Output documentation for the sample data

```
$ newstore-templates sample-documentation [options] <name>
```

Output documentation for the sample data.

### `preview` - Preview a template

```
$ newstore-templates preview [options] <name> <locale> [template] [data]
```

Previews a template for the given locale. If not provided the template code and the data is used from the API. If given a local file will be used. Additionally translations will be added.
To skip translation the  `--skip-translation` option can be used.

### `list-styles` - List all styles

```
$ newstore-templates list-styles [options]
```

List all styles.

### `update-style` - Update a style

```
$ newstore-templates preview [options] <name> <locale> [template] [data]
```

Update a style using a local file.

## Translations

The CLI tool includes the possibility to add translations to the templates. It uses a JSON file for each locale with the naming scheme

```
translations-<locale>.json
```

It uses the following structure:

```
{
  "common": {
    "foo": {
      "bar": "baz",
      ...
    }
  }
  "template1: {
    ...
  }
  ...
}

```

### Translation placeholders (template specific)

Template `template1`:
```
<span>[[[foo.bar]]]</span>
```

is replaced with the value of key `template1.foo.bar`.

### Common translations

Template `template1`:
```
<span>[[[#foo.bar]]]</span>
```

is replaced with the value of key `common.foo.bar`.
