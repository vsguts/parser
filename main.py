#!/usr/bin/env python3

import yaml
import json
import requests
import re
from parsel import Selector

# class Cache:

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
                product['error'] = error('Product ID not found. Iteration: {}'.format(iterator))
                continue

            if 'links' not in product:
                product['error'] = error("Product ID: {}: Key 'links' not found".format(product['id']))
                continue

            for link in product['links']:
                if 'shop' not in link:
                    link['error'] = error("Product ID: {}: Key 'shop' not found".format(product['id']))
                    continue

                site = self.sites.get_site(link['shop'])

                if site is None:
                    link['error'] = error("Product ID: {}: Shop not found for {}".format(product['id'], link['shop']))
                    continue

                if 'link' not in link:
                    link['error'] = error("Product ID: {}. Shop: {}. Key 'link' not found".format(product['id'], link['shop']))
                    continue

                price = self.get_price(link['link'], site)
                try:
                    debug("Product ID: {}. Shop: {}. Link: {} . Price was found: {}".format(product['id'], link['shop'], link['link'], price))
                    link['price'] = price
                except:
                    link['price'] = None
                    link['error'] = error("Product ID: {}. Shop: {}. PRICE NOT FOUND!".format(product['id'], link['shop']))

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


def error(text: str):
    # Logging TODO
    print(text)
    return text


def debug(text: str):
    # Logging TODO
    print(text)
    return text


if __name__ == '__main__':

    # Read config
    stream = open('./config.yml')
    config = yaml.unsafe_load(stream)

    # Prepare sites collection config
    sites_collection = SitesCollection(config['sites'])

    # Download schema
    response = requests.get(config['urls']['get'])

    data = response.json()

    parser = Parser(data['products'], sites_collection)
    result = parser.run()

    # Send response
    requests.post(config['urls']['set'], json=result)
    print(json.dumps(result, indent=4))
