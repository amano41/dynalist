# Dynalist Export

Python CLI tool for exporting Dynalist documents in OPML format.

## Obtaining API secret

Obtain your API secret token from [Dynalist developer page](https://dynalist.io/developer) and save it as `~/.dynalistrc` or store it to the environment variable `$DYNALIST_TOKEN`.

## Looking up item ID

Look up the ID of the document or folder you want to export with the `--find` option.
You can search for item names (not paths) using regular expressions.

```shell
$ dynalist --find NAME
```

## Exporting item

Use the `--export` option with an item ID to export the item.
If a folder ID is specified, all documents in that folder will be exported.

```shell
$ dynalist --export ID
```

The Dynalist API for downloading document content has a rate limit of 30 times per minute. Therefore, when exporting a folder, this script will sleep for 60 seconds for every 20 documents exported.

## Managing project folder

You can map a remote folder to a local directory to easily manage and export project documents.

Create a project settings file `.dynalist.json` in any local directory you want to map to the remote folder and specify the ID of the remote folder as the value for the key "root".

```json
{
  "root": "REMOTE_FOLDER_ID"
}
```

By using `--status` option, you can check for updates of all documents in the project folder.
This is done by querying the version number information stored on the Dynalist server.

```shell
$ dynalist --status
```

Run the script with the `--update` option to download the latest version of documents in the project folder to the local directory.

```shell
$ dynalist --update
```

The version number information for each document is stored in the project settings file `.dynalist.json` and used for the next update check with the `--status` option.
