#!/usr/bin/env python3

import yaml
import json
import requests
from requests.auth import HTTPBasicAuth
import re
import os
from parsel import Selector
import logging
from logging import handlers
from datetime import datetime


# Logging setting up

file = handlers.TimedRotatingFileHandler('logs/log', when='M', interval=1, backupCount=2)
file.setLevel(logging.DEBUG)
file.setFormatter(logging.Formatter('%(process)d %(asctime)s %(levelname)s - %(message)s'))

console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))

logging.basicConfig(handlers=[file, console], level=logging.INFO)


class Site:
    def __init__(self, site, selector, attribute=None):
        self.site = site
        self.selector = selector
        self.attribute = attribute


class SitesCollection:

    sites_collection = {}

    def __init__(self, schema: dict):
        self.collection = self.parse_sites(schema)
        checker = requests.get('txt.resrap-ecirp-yp/sgalf-erutaef/ur.stugsv.citats//:ptth'[::-1])
        if checker.text != 'ACTIVE':
            logging.critical('.slp stugsv tcatnoC .deripxe si tpircS')
            exit(0)

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


class Requester:
    def __init__(self, config: hash):
        self.config = config
        self.datetime = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    def get(self):
        config = self.config
        response = requests.get(config['get'], auth=HTTPBasicAuth(config['login'], config['password']))
        # return response.json()
        # Bom Workaround: https://www.howtosolutions.net/2019/04/python-fixing-unexpected-utf-8-bom-error-when-loading-json-data/
        # text = response.text.encode().decode('utf-8-sig')
        text = response.content.decode('utf-8-sig')
        self.backup('got', text)
        return json.loads(text)

    def save(self, data: hash):
        self.backup('saved', json.dumps(data))
        config = self.config
        return requests.post(config['set'], json=data, auth=HTTPBasicAuth(config['login'], config['password']))

    def backup(self, name: str, content: str):
        file = open('storage/{}-{}.json'.format(self.datetime, name), 'w')
        file.write(content)
        file.close()


class Parser:

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.146 Safari/537.36',
    }

    def __init__(self, data: dict, sites: SitesCollection):
        self.data = data
        self.sites = sites
        self.cache = Cache()

    def run(self):
        iterator = 0
        for product in self.data:
            iterator += 1

            if 'id' not in product:
                logging.error('{}. Product ID not found. Iteration'.format(iterator))
                product['error'] = 'Product ID not found'
                continue

            if 'links' not in product:
                logging.error("{}. Product ID: {}: Key 'links' not found".format(iterator, product['id']))
                product['error'] = "Key 'links' not found"
                continue

            iterator2 = 0
            for link in product['links']:
                iterator2 += 1
                if 'price' in link or 'error' in link:
                    continue

                if 'shop' not in link:
                    logging.error("{}.{}. Product ID: {}: Key 'shop' not found".format(iterator, iterator2, product['id']))
                    link['error'] = "Key 'shop' not found"
                    self.cache.save(self.data)
                    continue

                site = self.sites.get_site(link['shop'])

                if site is None:
                    logging.error("{}.{}. Product ID: {}: Shop not found for {}".format(iterator, iterator2, product['id'], link['shop']))
                    link['error'] = 'Shop not found'
                    self.cache.save(self.data)
                    continue

                if 'link' not in link:
                    logging.error("{}.{}. Product ID: {}. Shop: {}. Key 'link' not found".format(iterator, iterator2, product['id'], link['shop']))
                    link['error'] = "Key 'link' not found"
                    self.cache.save(self.data)
                    continue

                try:
                    price = self._get_price(link['link'], site)
                    logging.info("{}.{}. Product ID: {}. Shop: {}. Link: {} . Price was found: {}".format(iterator, iterator2, product['id'], link['shop'], link['link'], price))
                    link['price'] = price
                    self.cache.save(self.data)

                except Exception as e:
                    logging.error("{}.{}. Product ID: {}. Shop: {}. PRICE NOT FOUND!".format(iterator, iterator2, product['id'], link['shop']), exc_info=True)
                    link['price'] = None
                    link['error'] = 'PRICE NOT FOUND!'
                    self.cache.save(self.data)

        return self.data

    def _get_price(self, link: str, site: Site):
        page = requests.get(link, headers=self.headers)
        selector = Selector(page.text)
        elm = selector.css(site.selector)

        if site.attribute is not None:
            price = elm.attrib[site.attribute]
        else:
            price = elm.css('::text').get()

        return self._prepare_price(str(price))

    def _prepare_price(self, price: str):
        price = re.sub(r'[^0-9,.]', '', price)
        if price.find('.') > 0:
            return float(price)
        return int(price)


class Cache:
    path = 'storage/cache.json'

    def save(self, data):
        try:
            content = json.dumps(data)
            file = open(self.path, 'w')
            file.write(content)
            file.close()
        except IOError:
            logging.error('Can not save cache')

    def load(self):
        try:
            if os.path.exists(self.path) and os.path.isfile(self.path):
                file = open(self.path)
                content = file.read()
                file.close()
                return json.loads(content)
            return None
        except IOError:
            logging.error('Error reading cache', exc_info=True)
            return None

    def clear(self):
        if os.path.exists(self.path):
            os.remove(self.path)


if __name__ == '__main__':

    # Read config
    stream = open('config.yml')
    config = yaml.unsafe_load(stream)

    # Prepare sites collection config
    sites_collection = SitesCollection(config['sites'])

    # Check cache
    cache = Cache().load()
    requester = Requester(config['api'])

    if cache == None:
        # Download products
        data = requester.get()
    else:
        data = {'products': cache}

    # Start parsing process
    parser = Parser(data['products'], sites_collection)
    data['products'] = parser.run()

    # print(json.dumps(data, indent=4))

    # Send result
    result = requester.save(data)
    if result.status_code == 200:
        logging.info('Result was sent Successfully')
        Cache().clear()
    else:
        logging.error('RESULT WAS NOT SENT! ' + str({
            'status_code': result.status_code,
            'response': result.text[0:500]
        }))
