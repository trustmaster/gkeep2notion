#!/usr/local/bin/python3
from argparse import ArgumentParser
from configparser import ConfigParser
from enum import Enum
import os
import getpass
import re
import keyring
import urllib.request

from gkeepapi import Keep, node
from notion_client import Client


class BlockType(str, Enum):
    """Notion Block Type"""
    Paragraph = 'paragraph'
    H1 = "heading_1"
    H2 = "heading_2"
    H3 = "heading_3"
    BulletedListItem = "bulleted_list_item"
    NumberedListItem = "numbered_list_item"
    ToDo = "to_do"
    Toggle = "toggle"
    ChildPage = "child_page"
    ChildDatabase = "child_database"
    Embed = "embed"
    Image = "image"
    Video = "video"
    File = "file"
    PDF = "pdf"
    Bookmark = "bookmark"
    Callout = "callout"
    Quote = "quote"
    Equation = "equation"
    Divider = "divider"
    TableOfContents = "table_of_contents"
    Column = "column"
    ColumnList = "column_list"
    LinkPreview = "link_preview"
    SyncedBlock = "synced_block"
    Template = "template"
    LinkToPage = "link_to_page"
    Table = "table"
    TableRow = "table_row"
    Unsupported = "unsupported"


class RichText:
    """Notion rich text blocks"""
    urlRegex = re.compile(
        r'(https?://[\w\-\.]+\.[a-z]+(?:/[\w_\.%\-&\?=/#]*)*)', flags=re.MULTILINE)

    def __init__(self, text: str):
        self._chunks = []
        self._parse(text)

    def _parse(self, text: str):
        # Split in chunks by URLs
        chunks = RichText.urlRegex.split(text)
        for c in chunks:
            if RichText.urlRegex.fullmatch(c):
                # Add as URL
                self.add_chunk(c, c)
            else:
                self.add_chunk(c)

    @property
    def chunks(self) -> list[dict]:
        return self._chunks

    def add_chunk(self, text: str, url: str = ''):
        if url != '':
            self._chunks.append({
                "type": "text",
                "text": {
                    "content": text,
                    "link": {
                        "type": "url",
                        "url": url
                    }
                }
            })
            return

        self._chunks.append({
            "type": "text",
            "text": {
                    "content": text
            }
        })


class Page:
    """Notion Page model"""

    def __init__(self, title: str, parent_id: str):
        self._id = ''
        self._title = title
        self._parent_id = parent_id
        self._children = []

    def render(self) -> dict:
        return {
            "properties": {
                "title": [{"text": {"content": self._title}}]
            },
            "parent": {
                "type": "page_id",
                "page_id": self._parent_id
            },
            "children": self._children
        }

    @property
    def parent(self) -> dict:
        return {
            "type": "page_id",
            "page_id": self._parent_id
        }

    @property
    def properties(self) -> dict:
        return {
            "title": [{"text": {"content": self._title}}]
        }

    @property
    def children(self) -> dict:
        return self._children

    @property
    def title(self) -> str:
        return self._title

    @property
    def id(self) -> str:
        return self._id

    @id.setter
    def id(self, id: str):
        self._id = id

    def add_text(self, text: str, type: BlockType = BlockType.Paragraph):
        richText = RichText(text)
        self._children.append({
            "object": "block",
            "type": type,
            type: {
                "rich_text": richText.chunks
            }
        })

    def add_todo(self, text: str, checked: bool):
        richText = RichText(text)
        self._children.append({
            "object": "block",
            "type": BlockType.ToDo,
            BlockType.ToDo: {
                "rich_text": richText.chunks,
                "checked": checked
            }
        })


def create_page(notion: Client, page: Page) -> Page:
    """Creates a page in Notion and saves page.id"""
    notion_page = notion.pages.create(parent=page.parent,
                                      properties=page.properties,
                                      children=page.children)
    page.id = notion_page['id']
    return page


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


def parseBlock(p: str) -> dict:
    """Parses a line from a Keep Note into a Notion block type and text

    Supported block types:
    - Paragraph
    - BulletedListItem: starting with - or *
    - NumberedListItem: starting with a 1. or other number and dot
    - Quote: starting with >
    """
    m = re.match(r'^(\d+)\.\s+(.+)', p)
    if m:
        return {
            'type': BlockType.NumberedListItem,
            'text': m.group(2),
        }
    # TODO: support nested lists
    m = re.match(r'^\s*(\*|-)\s+(.+)', p)
    if m:
        return {
            'type': BlockType.BulletedListItem,
            'text': m.group(2),
        }
    m = re.match(r'^>\s+(.+)', p)
    if m:
        return {
            'type': BlockType.Quote,
            'text': m.group(1)
        }
    return {
        'type': BlockType.Paragraph,
        'text': p,
    }


def parseTextToPage(text: str, page: Page):
    lines = text.splitlines()
    print(f"Parsing {len(lines)} blocks")
    for p in lines:
        block = parseBlock(p)
        page.add_text(block['text'], block['type'])


def getNoteCategories(note: node.TopLevelNode) -> list[str]:
    categories = []
    for label in note.labels.all():
        categories.append(label.name)
    return categories


def importPageWithCategories(notion: Client, note: node.TopLevelNode, root: Page, categories: dict[str, Page]) -> Page:
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
            parent = Page(parentName, root.id)
            create_page(notion, parent)
            categories[parentKey] = parent
        cats = cats[1:]

    return Page(note.title, parent.id)


def parseNote(note: node.TopLevelNode, page: Page, keep: Keep, config: Config):
    # TODO add background colors (currently unsupported by notion-py)
    # color = str(note.color)[len('ColorValue.'):].lower()
    # if color != 'default':
    #     parent.background = color

    if config.import_media:
        # Images
        if len(note.images) > 0:
            print('Uploading images is unsupported by Notion API :(')
            # for blob in note.images:
            #     print('Importing image ', blob.text)
            #     url = keep.getMediaLink(blob)
            #     downloadFile(url, 'image.png')
            #     img: ImageBlock = page.children.add_new(
            #         ImageBlock, title=blob.text)
            #     img.upload_file('image.png')

        # Audio
        if len(note.audio) > 0:
            print('Uploading audio is unsupported by Notion API :(')
            # for blob in note.audio:
            #     print('Importing audio ', blob.text)
            #     url = keep.getMediaLink(blob)
            #     downloadFile(url, 'audio.mp3')
            #     img: AudioBlock = page.children.add_new(
            #         AudioBlock, title=blob.text)
            #     img.upload_file('audio.mp3')

    # Text
    text = note.text
    # Render page blocks
    parseTextToPage(text, page)


def parseList(list: node.List, page: Page):
    item: node.ListItem
    for item in list.items:  # type: node.ListItem
        page.add_todo(item.text, item.checked)


def url2uuid(url: str) -> str:
    """Extract UUID part from the notion URL"""
    m = re.match(r'^https://(www\.)?notion.so/(.+)([0-9a-f]{32})/?$', url)
    if not m:
        return ''
    id = m[3]
    return f"{id[0:8]}-{id[8:12]}-{id[12:16]}-{id[16:20]}-{id[20:32]}"


argparser = ArgumentParser(
    description='Export from Google Keep and import to Notion')
argparser.add_argument('-l', '--labels', type=str,
                       help='Search by labels, comma separated')
argparser.add_argument('-q', '--query', type=str, help='Search by title query')

args = argparser.parse_args()

config = get_config()

root_uuid = url2uuid(config.root_url)

keep = Keep()
login(keep, config.email)

print('Logging into Notion')
notion = Client(auth=config.token)

notes = Page('Notes', root_uuid)
todos = Page('TODOs', root_uuid)
create_page(notion, notes)
create_page(notion, todos)

categories = {
    'Notes': notes,
    'TODOs': todos
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
        page = importPageWithCategories(notion, gnote, todos, categories)
        parseList(gnote, page)
        create_page(notion, page)
    else:
        if not config.import_notes:
            continue
        print(f'Importing note #{i}: {gnote.title}')
        page = importPageWithCategories(notion, gnote, notes, categories)
        parseNote(gnote, page, keep, config)
        create_page(notion, page)
