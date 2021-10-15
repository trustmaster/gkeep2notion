# Google Keep -> Notion

Exports notes and lists from Google Keep and imports them into your Notion.

## Features

Supports exporting:

- Notes
- TODO lists
- Images and audio
- Categorization via labels

## Installation

This script requires Python 3.9+, https://github.com/kiwiz/gkeepapi, https://github.com/jamalex/notion-py, and a couple more libraries to run. Install the pre-requisite libraries via [Pip3](https://pypi.org/project/pip/):

```
pip3 install -r requirements.txt
```

Optional: make the script executable:

```
chmod +x gkeep2notion.py
```

### Preventing "Authentication failed" on some systems

On some systems the authentication fails even with valid credentials. This may happen because of two reasons: either Google issues a CAPTCHA for your IP address, or SSL certificate validation fails.

To fix the CAPTCHA problem, try using the [Unlock CAPTCHA link](https://accounts.google.com/DisplayUnlockCaptcha) before retrying login.

To try fixing the SSL problem, revert to an older version of the following library:

```
pip3 install requests==2.23.0
```

## Configuration

Before use, copy _config.example.ini_ to _config.ini_ and edit its contents. See configuration explanation below:

```ini
[gkeep]
email=your_name@gmail.com # Your Google account
import_notes=true # Set to false if you don't want to import notes
import_todos=true # Set to false if you don't want to import TODO lists
import_media=true # Set to false if you don't need to import images and audio

[notion]
token=Copy it from Notion cookies: token_v2 # See documentation below
root_url=https://notion.so/PAGE-ID Create a root url in your Notion # See documentation below
```

### Obtaining Notion token

The importer needs to access your Notion account and it needs to know the root URL in which to import all the Google Keep contents.

To get the access token, you need to copy the value of `token_v2` cookie for https://notion.so website. Example actions for Google Chrome:

1. Log into your Notion account at https://notion.so
1. Open Chrome Developer Tools and find _Application -> Cookies -> https://www.notion.so_
1. Find `token_v2` in the variables list and copy the value. Paste the value to `token` in _config.ini_

### Configuring the root_url

This script imports all the content under a certain page in Notion that has to exist already. It is recommended to create a special page for the imported content, and then migrate it to your regular Notion structure from there.

Navigate to your import root in the Notion tree, and choose "Copy link" in the context menu. Paste that link to `root_url` in the _config.ini_.

## Usage

### Google authentication

The first time you run `gkeep2notion` it will ask for your Google Account's password to authenticate into your Google Keep account. After obtaining an authentication token, `gkeep2notion` saves it in your system's keyring. Next time you won't need to enter the password again.

### Import everything

_Note: export/import takes a considerable amount of time. Especially when working with notes containing media files. So you may want to try importing a subset of your records before importing everything._

By default gkeep2notion exports everything in your Google Keep account and imports it into Notion. It can be done as simple as:

```bash
./gkeep2notion.py
```

### Google Keep search query

You can use the search function built into Google Keep to import notes matching a search query:

```bash
./gkeep2notion.py -q 'Orange apple'
```

### Import specific labels

You can import notes and tasklists containing specific label(s) in Google Keep using the `-l` option.

An example with one label:

```bash
./gkeep2notion.py -l cooking
```

An example with multiple labels, comma separated:

```bash
./gkeep2notion.py -l 'work, business, management'
```

## Credits

This tool uses the [unofficial Google Keep API for Python](https://github.com/kiwiz/gkeepapi) by [kiwiz](https://github.com/kiwiz). Google Keep is of course a registered trademark of Google and neither the API nor this script are affiliated with Google, Inc.

Thanks to [jamalex](https://github.com/jamalex) for the [unofficial Notion Python API](https://github.com/jamalex/notion-py). Neither that API nor this script are affiliated with Notion. Notion is a trademark of Notion Labs, Inc.
