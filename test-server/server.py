#!/usr/bin/env python3

import json
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route('/')
def index():
    return jsonify({
        'server': 'test',
        'version': '0.0.1-beta'
    })


@app.route('/get')
def get():
    stream = open('get.json')
    return jsonify(json.load(stream))


@app.route('/set', methods=['POST'])
def save():
    # Parse json option
    # data = json.dumps(request.json)
    # file = open('result.json', 'w')

    # Binary option
    data = request.data
    file = open('result.json', 'w+b')

    status = file.write(data)
    file.close()

    return jsonify({'status': status})


if __name__ == '__main__':
    app.run()
