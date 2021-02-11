#!/usr/bin/env python3

import yaml
import requests


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
    def __init__(self, data: dict, sites: SitesCollection):
        self.data = data
        self.sites = sites

    def run(self):
        iterator = 0
        for product in self.data:
            iterator += 1

            if 'id' not in product:
                print('Product ID not found. Iteration: {}'.format(iterator))
                continue

            if 'links' not in product:
                print("Product ID: {}: Key 'links' not found".format(product['id']))
                continue

            for link in product['links']:
                if 'shop' not in link:
                    print("Product ID: {}: Key 'shop' not found".format(product['id']))
                    continue

                site = self.sites.get_site(link['shop'])

                if site is None:
                    print("Product ID: {}: Shop not found for {}".format(product['id'], link['shop']))
                    continue

                if 'link' not in link:
                    print("Product ID: {}. Shop: {}. Key 'link' not found".format(product['id'], link['shop']))
                    continue

                price = self.get_price(link['link'], site)
                exit()

        return self.data

    def get_price(self, link: str, site: Site):
        print(link, site)


if __name__ == '__main__':

    # Read config
    stream = open('./config.yml')
    config = yaml.safe_load(stream)

    # Prepare sites collection config
    sites_collection = SitesCollection(config['sites'])

    # Download schema
    response = requests.request('get', config['urls']['get'])

    data = response.json()

    parser = Parser(data['products'], sites_collection)
    result = parser.run()

