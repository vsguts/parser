#!/usr/bin/env python3

import yaml
import json
import requests
import re
from parsel import Selector
import logging
from logging import handlers


# Logging setting up

file = handlers.TimedRotatingFileHandler('logs/log', when='M', interval=1, backupCount=2)
file.setLevel(logging.DEBUG)
file.setFormatter(logging.Formatter('%(process)d %(asctime)s %(levelname)s - %(message)s'))

console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))

logging.basicConfig(handlers=[file, console], level=logging.DEBUG)


class Site:
    def __init__(self, site, selector, attribute=None):
        self.site = site
        self.selector = selector
        self.attribute = attribute


class SitesCollection:

    sites_collection = {}

    def __init__(self, schema: dict):
        self.collection = self.parse_sites(schema)

    def parse_sites(self, schema: dict):
        collection = {}
        for item in schema:
            site = item['site']
            selector = item.get('selector', '')
            attribute = item.get('attribute', None)
            collection[site] = Site(site, selector, attribute)

        return collection

    def get_site(self, key):
        return self.collection.get(key, None)


class Parser:

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.146 Safari/537.36',
    }

    def __init__(self, data: dict, sites: SitesCollection):
        self.data = data
        self.sites = sites

    def run(self):
        iterator = 0
        for product in self.data:
            iterator += 1

            if 'id' not in product:
                logging.error('Product ID not found. Iteration: {}'.format(iterator))
                product['error'] = 'Product ID not found'
                continue

            if 'links' not in product:
                logging.error("Product ID: {}: Key 'links' not found".format(product['id']))
                product['error'] = "Key 'links' not found"
                continue

            for link in product['links']:
                if 'shop' not in link:
                    logging.error("Product ID: {}: Key 'shop' not found".format(product['id']))
                    link['error'] = "Key 'shop' not found"
                    continue

                site = self.sites.get_site(link['shop'])

                if site is None:
                    logging.error("Product ID: {}: Shop not found for {}".format(product['id'], link['shop']))
                    link['error'] = 'Shop not found'
                    continue

                if 'link' not in link:
                    logging.error("Product ID: {}. Shop: {}. Key 'link' not found".format(product['id'], link['shop']))
                    link['error'] = "Key 'link' not found"
                    continue

                try:
                    price = self.get_price(link['link'], site)
                    logging.info("Product ID: {}. Shop: {}. Link: {} . Price was found: {}".format(product['id'], link['shop'], link['link'], price))
                    link['price'] = price
                except Exception as e:
                    logging.error("Product ID: {}. Shop: {}. PRICE NOT FOUND!".format(product['id'], link['shop']), exc_info=True)
                    link['price'] = None
                    link['error'] = 'PRICE NOT FOUND!'

        return self.data

    def get_price(self, link: str, site: Site):
        page = requests.get(link, headers=self.headers)
        selector = Selector(page.text)
        elm = selector.css(site.selector)

        if site.attribute is not None:
            price = elm.attrib[site.attribute]
        else:
            price = elm.css('::text').get()

        return self.prepare_price(str(price))

    def prepare_price(self, price: str):
        price = re.sub(r'[^0-9,.]', '', price)
        if price.find('.') > 0:
            return float(price)
        return int(price)


if __name__ == '__main__':

    # Read config
    stream = open('./config.yml')
    config = yaml.unsafe_load(stream)

    # Prepare sites collection config
    sites_collection = SitesCollection(config['sites'])

    # Download products
    response = requests.get(config['urls']['get'])
    data = response.json()

    # Start parsing process
    parser = Parser(data['products'], sites_collection)
    data['products'] = parser.run()

    # print(json.dumps(data, indent=4))

    # Send result
    result = requests.post(config['urls']['set'], json=data)
    if result.status_code == 200:
        logging.info('Result was sent Successfully')
    else:
        logging.error('Result was not sent!')
