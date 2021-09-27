import argparse
import sys

from gdoc2mdown import gdoc
from gdoc2mdown import gdoc2mdown
from gdoc2mdown import newsletter


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
    document = gdoc.get_doc(args.docid)

    text = gdoc2mdown.read_strucutural_elements(document.get('body').get('content'))

    structured_doc = newsletter.parse_newsletter(text)
    print(newsletter.format_newsletter(structured_doc))


if __name__ == '__main__':
    main()
