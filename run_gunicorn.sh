#!/bin/bash
gunicorn rarbg:app -b localhost:6000 -k aiohttp.worker.GunicornWebWorker --access-logfile -
