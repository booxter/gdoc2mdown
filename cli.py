import argparse
import datetime
from datetime import datetime as dt
import os.path
import re
import sys

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

today = dt.today()
months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]
months_join = '|'.join(months)

categories = [
    'Announcements & Events',
    'Top Stories',
    'Border Crisis',
    'Repressions in Belarus',
    'Analysis',
    'Belarus and the United States',
    'Belarus and Russia',
    'Belarus and Europe',
    'Interesting Read',
]
cats_join = '|'.join(categories)


def read_paragraph_element(element):
    """Returns the text in the given ParagraphElement.
        Args:
            element: a ParagraphElement from a Google Doc.
    """
    text_run = element.get('textRun')
    if not text_run:
        return ''
    return text_run.get('content')


def read_strucutural_elements(elements):
    """Recurses through a list of Structural Elements to read a document's text where text may be
        in nested elements.
        Args:
            elements: a list of Structural Elements.
    """
    text = ''
    for value in elements:
        if 'paragraph' in value:
            elements = value.get('paragraph').get('elements')
            for elem in elements:
                text += read_paragraph_element(elem)
        elif 'table' in value:
            # The text in table cells are in nested Structural Elements and tables may be
            # nested.
            table = value.get('table')
            for row in table.get('tableRows'):
                cells = row.get('tableCells')
                for cell in cells:
                    text += read_strucutural_elements(cell.get('content'))
        elif 'tableOfContents' in value:
            # The text in the TOC is also in a Structural Element.
            toc = value.get('tableOfContents')
            text += read_strucutural_elements(toc.get('content'))
    return text


def category(name):
    return {'name': name, 'articles': []}


def article(month, day, headline):
    return {'month': month, 'day': day, 'headline': headline, 'link': '', 'text': ''}


def last_week_range():
    first_day = today - datetime.timedelta(days=7)
    last_day = today - datetime.timedelta(days=1)
    if first_day.month == last_day.month:
        return '{}-{}'.format(first_day.strftime('%b %d'), last_day.strftime('%d'))
    return '{}-{}'.format(first_day.strftime('%b %d'), last_day.strftime('%b %d'))


def parse_newsletter(text):
    # start with a single unnamed category
    category_name = ''
    newsletter = {
        'categories': [category(category_name)],
        'number': -1,
        'date_range': last_week_range(),
    }

    header_found = False
    for line in text.split('\n'):
        line = line.strip()
        if not line:
             continue

        date_range_re = re.compile(r'^({0})\s+(\d+)\s+\-\s+({0})\s+(\d+)\s*$'.format(months_join))
        
        match = date_range_re.match(line)
        if match:
             start_month, start_day, end_month, end_day = match.group(1, 2, 3, 4)
             if start_month == end_month:
                 newsletter['date_range'] = '{} {}-{}'.format(start_month, start_day, end_day)
             else:
                 newsletter['date_range'] = '{} {}-{} {}'.format(start_month, start_day, end_month, end_day)
             continue

        if not header_found:
            header_re = re.compile(r'^Newsletter #(\d+)')
            match = header_re.match(line)
            if match:
                 newsletter['number'] = int(match.group(1))
                 header_found = True
            continue

        category_re = re.compile(r'^({})$'.format(cats_join))
        match = category_re.match(line)
        if match:
            category_name = match.group(1)
            newsletter['categories'].append(category(category_name))
            continue

        articles = newsletter['categories'][-1]['articles']
        
        news_entry_re = re.compile(r'^({})\s+(\d+):\s+(.*)$'.format(months_join))
        match = news_entry_re.match(line)
        if match:
            month, day, headline = match.group(1, 2, 3)
            articles.append(article(month, day, headline))
            continue

        if not articles:
            articles.append(article(None, None, None))

        latest_article = articles[-1]
        link_re = re.compile(r'^(https?://\S+)$')
        match = link_re.match(line)
        if match:
            link = match.group(0)
            latest_article['link'] = link
            continue

        latest_article['text'] += '{}\n'.format(line)

    return newsletter


def format_newsletter(doc):
    text = '''---
title: "Key Events: {}"
date: {}
draft: false
categories: [Newsletter]
---
'''.format(doc['date_range'], today.strftime('%Y-%m-%d'))

    num = '{:03}'.format(doc['number'])
    text += '\n{{{{< figure src="/img/{0}/{0}-1.jpeg" caption="*This past week: ...*" >}}}}\n\n'.format(num)

    for category in doc['categories']:
        if category['name']:
            text += '\n### {}\n\n'.format(category['name'])
        for article in category['articles']:
            if article['month'] and article['day']:
                text += '**{} {}:** '.format(article['month'], article['day'])

            if article['headline'] and article['link']:
                text += '[*{}*]({})\n'.format(article['headline'], article['link'])
            elif article['headline']:
                text += '*{}*\n'.format(article['headline'])
            elif article['link']:
                text += '[*{}*]({})\n'.format(article['link'], article['link'])
            else:
                text += '\n'

            if article['text']:
                text += article['text']

            text += '\n' # one line between entries
    return text


def parse_args(args):
    parser = argparse.ArgumentParser(description='BFF newsletter: gdoc -> markdown.')
    parser.add_argument('--docid', dest='docid',
                        help='Google Document ID', required=True)
    return parser.parse_args()


def main(args=sys.argv[1:]):
    """Shows basic usage of the Docs API.
    Prints the title of a sample document.
    """
    args = parse_args(args)
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('docs', 'v1', credentials=creds)

    # Retrieve the documents contents from the Docs service.
    document = service.documents().get(documentId=args.docid).execute()

    text = read_strucutural_elements(document.get('body').get('content'))

    structured_doc = parse_newsletter(text)
    print(format_newsletter(structured_doc))


if __name__ == '__main__':
    main()
