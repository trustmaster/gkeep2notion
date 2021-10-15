#!/usr/local/bin/python3
from argparse import ArgumentParser
from configparser import ConfigParser
import os
import getpass
import re
import keyring
import urllib.request

from gkeepapi import Keep, node
from notion.block import AudioBlock, BulletedListBlock, ImageBlock, NumberedListBlock, PageBlock, QuoteBlock, TextBlock, TodoBlock
from notion.client import NotionClient


class Config:
    def __init__(self, ini: ConfigParser):
        self.email = ini['gkeep']['email']
        self.import_notes = ini['gkeep']['import_notes'].lower() == 'true'
        self.import_todos = ini['gkeep']['import_todos'].lower() == 'true'
        self.import_media = ini['gkeep']['import_media'].lower() == 'true'
        self.token = ini['notion']['token']
        self.root_url = ini['notion']['root_url']


def get_config(path='config.ini') -> Config:
    if not os.path.isfile(path):
        print(f'Config file {path} not found')
        exit()

    ini = ConfigParser(interpolation=None, inline_comment_prefixes=('#', ';'))
    ini.read(path)

    return Config(ini)


def authenticate(keep: Keep, email: str):
    print('Logging into Google Keep')
    password = getpass.getpass('Password: ')
    print('Authenticating, this may take a while...')
    try:
        keep.login(email, password)
    except Exception as e:
        print('Authentication failed')
        print(e)
        exit()

    # Save the auth token in keyring
    print('Authentication is successful, saving token in keyring')
    token = keep.getMasterToken()
    keyring.set_password('gkeep2notion', email, token)
    print('Token saved. Have fun with other commands!')


def login(keep: Keep, email: str):
    print('Loading access token from keyring')
    token = keyring.get_password('gkeep2notion', email)
    if token:
        print('Authorization, this may take a while...')
        try:
            keep.resume(email, token)
        except:
            authenticate(keep, email)
    else:
        authenticate(keep, email)


def downloadFile(url, path):
    urllib.request.urlretrieve(url, path)


def renderUrls(text: str) -> str:
    return re.sub(r'(https?://[\w\-\.]+\.[a-z]+(/[\w_\.%\-&\?=/#]*)*)', r'[\1](\1)', text, flags=re.MULTILINE)

# Supported block types:
# - TextBlock
# - BulletedListBlock: starting with - or *
# - NumberedListBlock
# - QuoteBlock: starting with >


def parseBlock(p: str) -> dict:
    if re.match(r'^(\d+)\.', p):
        return {
            'type': NumberedListBlock,
            'title': p,
        }
    # TODO: support nested lists
    m = re.match(r'^\s*(\*|-)\s+(.+)', p)
    if m:
        return {
            'type': BulletedListBlock,
            'title': m.group(2),
        }
    m = re.match(r'^>\s+(.+)', p)
    if m:
        return {
            'type': QuoteBlock,
            'title': m.group(1)
        }
    return {
        'type': TextBlock,
        'title': p,
    }


def parsePage(text: str) -> list[dict]:
    lines = text.splitlines()
    print(f"Parsing {len(lines)} blocks")
    return [parseBlock(p) for p in lines]


def renderBlocks(page: PageBlock, blocks: list[dict]):
    for b in blocks:
        page.children.add_new(b['type'], title=b['title'])


def getNoteCategories(note: node.TopLevelNode) -> list[str]:
    categories = []
    for label in note.labels.all():
        categories.append(label.name)
    return categories


def importCategories(note: node.TopLevelNode, root: PageBlock, default: str, categories: dict[str, PageBlock]) -> PageBlock:
    # Extract categories
    rootName = root.title
    cats = getNoteCategories(note)

    # Use first category as the main (parent)
    if len(cats) == 0:
        parent = root
    else:
        parentName = cats[0]
        parentKey = f"{rootName}.{parentName}"
        if parentKey in categories:
            parent = categories[parentKey]
        else:
            parent = root.children.add_new(PageBlock, title=parentName)
            categories[parentKey] = parent
        cats = cats[1:]
    page: PageBlock = parent.children.add_new(PageBlock, title=note.title)

    # Insert to other categories as alias
    for catName in cats:
        catKey = f"{rootName}.{catName}"
        if catKey in categories:
            cat = categories[catKey]
        else:
            cat = root.children.add_new(PageBlock, title=catName)
            categories[catKey] = cat
        cat.children.add_alias(page)

    return page


def parseNote(note: node.TopLevelNode, page: PageBlock, keep: Keep, config: Config):
    # TODO add background colors (currently unsupported by notion-py)
    # color = str(note.color)[len('ColorValue.'):].lower()
    # if color != 'default':
    #     parent.background = color

    if config.import_media:
        # Images
        if len(note.images) > 0:
            for blob in note.images:
                print('Importing image ', blob.text)
                url = keep.getMediaLink(blob)
                downloadFile(url, 'image.png')
                img: ImageBlock = page.children.add_new(
                    ImageBlock, title=blob.text)
                img.upload_file('image.png')

        # Audio
        if len(note.audio) > 0:
            for blob in note.audio:
                print('Importing audio ', blob.text)
                url = keep.getMediaLink(blob)
                downloadFile(url, 'audio.mp3')
                img: AudioBlock = page.children.add_new(
                    AudioBlock, title=blob.text)
                img.upload_file('audio.mp3')

    # Text
    text = note.text
    # Render URLs
    text = renderUrls(text)
    # Render page blocks
    blocks = parsePage(text)
    renderBlocks(page, blocks)


def parseList(list: node.List, page: PageBlock):
    item: node.ListItem
    for item in list.items:  # type: node.ListItem
        page.children.add_new(TodoBlock, title=item.text, checked=item.checked)


argparser = ArgumentParser(
    description='Export from Google Keep and import to Notion')
argparser.add_argument('-l', '--labels', type=str,
                       help='Search by labels, comma separated')
argparser.add_argument('-q', '--query', type=str, help='Search by title query')

args = argparser.parse_args()

config = get_config()

keep = Keep()
login(keep, config.email)

print('Logging into Notion')
client = NotionClient(token_v2=config.token)

root = client.get_block(config.root_url)

notes = root.children.add_new(PageBlock, title='Notes')
todos = root.children.add_new(PageBlock, title='TODOs')

categories = {
}

glabels = []
if args.labels:
    labels = args.labels.split(',')
    labels = [l.strip() for l in labels]
    labels = list(filter(lambda l: l != '', labels))
    for l in labels:
        glabel = keep.findLabel(l)
        glabels.append(glabel)

query = ''
if args.query:
    query = args.query.strip()

gnotes = []
if len(glabels) > 0:
    gnotes = keep.find(labels=glabels)
elif len(query) > 0:
    gnotes = keep.find(query=query)
else:
    gnotes = keep.all()

i = 0
for gnote in gnotes:
    i += 1
    if isinstance(gnote, node.List):
        if not config.import_todos:
            continue
        print(f'Importing TODO #{i}: {gnote.title}')
        page = importCategories(gnote, todos, 'TODOs', categories)
        parseList(gnote, page)
    else:
        if not config.import_notes:
            continue
        print(f'Importing note #{i}: {gnote.title}')
        page = importCategories(gnote, notes, 'Notes', categories)
        parseNote(gnote, page, keep, config)

    if i == 12:
        break
