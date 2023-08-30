#!/usr/bin/env python3
# coding: utf-8
# pyright: reportMissingImports=false

"""Woob Bank Exporter"""

import logging
import os
import sys
import threading
import time
from datetime import datetime
from typing import Callable
from wsgiref.simple_server import make_server

import pytz
from prometheus_client import PLATFORM_COLLECTOR, PROCESS_COLLECTOR
from prometheus_client.core import REGISTRY, CollectorRegistry, Metric
from prometheus_client.exposition import _bake_output, parse_qs
from woob.core import Woob
from woob.exceptions import ModuleLoadError

WOOB_BANK_EXPORTER_NAME = os.environ.get(
    "WOOB_BANK_EXPORTER_NAME", "woob-bank-exporter"
)
WOOB_BANK_EXPORTER_LOGLEVEL = os.environ.get(
    "WOOB_BANK_EXPORTER_LOGLEVEL", "INFO"
).upper()
WOOB_BANK_EXPORTER_TZ = os.environ.get("TZ", "Europe/Paris")

MANDATORY_ENV_VARS = [
    "WOOB_BANK_MODULE",
    "WOOB_BANK_NAME",
    "WOOB_BANK_LOGIN",
    "WOOB_BANK_PASSWORD",
]

IGNORE_KEYS = ["url"]


def make_wsgi_app(
    registry: CollectorRegistry = REGISTRY, disable_compression: bool = False
) -> Callable:
    """Create a WSGI app which serves the metrics from a registry."""

    def prometheus_app(environ, start_response):
        # Prepare parameters
        accept_header = environ.get("HTTP_ACCEPT")
        accept_encoding_header = environ.get("HTTP_ACCEPT_ENCODING")
        params = parse_qs(environ.get("QUERY_STRING", ""))
        headers = [
            ("Server", ""),
            ("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0"),
            ("Pragma", "no-cache"),
            ("Expires", "0"),
            ("X-Content-Type-Options", "nosniff"),
        ]
        if environ["PATH_INFO"] == "/":
            status = "301 Moved Permanently"
            headers.append(("Location", "/metrics"))
            output = b""
        elif environ["PATH_INFO"] == "/favicon.ico":
            status = "200 OK"
            output = b""
        elif environ["PATH_INFO"] == "/metrics":
            status, tmp_headers, output = _bake_output(
                registry,
                accept_header,
                accept_encoding_header,
                params,
                disable_compression,
            )
            headers += tmp_headers
        else:
            status = "404 Not Found"
            output = b""
        start_response(status, headers)
        return [output]

    return prometheus_app


def start_wsgi_server(
    port: int,
    addr: str = "0.0.0.0",  # nosec B104
    registry: CollectorRegistry = REGISTRY,
) -> None:
    """Starts a WSGI server for prometheus metrics as a daemon thread."""
    app = make_wsgi_app(registry)
    httpd = make_server(addr, port, app)
    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()


start_http_server = start_wsgi_server

# Logging Configuration
try:
    pytz.timezone(WOOB_BANK_EXPORTER_TZ)
    logging.Formatter.converter = lambda *args: datetime.now(
        tz=pytz.timezone(WOOB_BANK_EXPORTER_TZ)
    ).timetuple()
    logging.basicConfig(
        stream=sys.stdout,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
        level=WOOB_BANK_EXPORTER_LOGLEVEL,
    )
except pytz.exceptions.UnknownTimeZoneError:
    logging.Formatter.converter = lambda *args: datetime.now(
        tz=pytz.timezone("Europe/Paris")
    ).timetuple()
    logging.basicConfig(
        stream=sys.stdout,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
        level="INFO",
    )
    logging.error("TZ invalid : %s !", WOOB_BANK_EXPORTER_TZ)
    os._exit(1)
except ValueError:
    logging.basicConfig(
        stream=sys.stdout,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
        level="INFO",
    )
    logging.error("WOOB_BANK_EXPORTER_LOGLEVEL invalid !")
    os._exit(1)

# Check Mandatory Environment Variable
for var in MANDATORY_ENV_VARS:
    if var not in os.environ:
        logging.critical("%s environement variable must be set !", var)
        os._exit(1)

WOOB_BANK_MODULE = os.environ.get("WOOB_BANK_MODULE")
WOOB_BANK_LOGIN = os.environ.get("WOOB_BANK_LOGIN")
WOOB_BANK_PASSWORD = os.environ.get("WOOB_BANK_PASSWORD")
WOOB_BANK_NAME = os.environ.get("WOOB_BANK_NAME")

# Check UPTIME_ROBOT_EXPORTER_PORT
try:
    WOOB_BANK_EXPORTER_PORT = int(os.environ.get("WOOB_BANK_EXPORTER_PORT", "8123"))
except ValueError:
    logging.error("WOOB_BANK_EXPORTER_PORT must be int !")
    os._exit(1)

METRICS = [
    {
        "name": "balance",
        "description": "Balance on this bank account",
        "type": "gauge",
    },
    {
        "name": "coming",
        "description": "Sum of coming movements",
        "type": "gauge",
    },
    {
        "name": "valuation_diff_ratio",
        "description": "+/- values ratio",
        "type": "gauge",
    },
    {
        "name": "total_amount",
        "description": "Total amount loaned",
        "type": "gauge",
    },
    {
        "name": "next_payment_amount",
        "description": "Amount of next payment",
        "type": "gauge",
    },
    {
        "name": "opening_date",
        "description": "Date when the account contract was created on the bank",
        "type": "datetime",
    },
    {
        "name": "subscription_date",
        "description": "Date of subscription of the loan",
        "type": "datetime",
    },
    {
        "name": "maturity_date",
        "description": "Estimated end date of the loan",
        "type": "datetime",
    },
    {
        "name": "next_payment_date",
        "description": "Date of the next payment",
        "type": "datetime",
    },
]

# REGISTRY Configuration
REGISTRY.unregister(PROCESS_COLLECTOR)
REGISTRY.unregister(PLATFORM_COLLECTOR)
REGISTRY.unregister(REGISTRY._names_to_collectors["python_gc_objects_collected_total"])


class WoobBankCollector:
    """Woob Bank Collector Class"""

    def __init__(self):
        try:
            self.woob = Woob().load_backend(
                WOOB_BANK_MODULE,
                WOOB_BANK_NAME,
                params={"login": WOOB_BANK_LOGIN, "password": WOOB_BANK_PASSWORD},
            )
        except ModuleLoadError as exception:
            logging.error("%s (%s)", exception, exception.module)
            os._exit(1)

        if not self.woob.check_credentials():
            logging.error("Invalid Credentials !")
            os._exit(1)

    def get_metrics(self):
        """Retrieve Prometheus Metrics"""
        metrics = []
        for account in self.woob.iter_accounts():
            labels = {}
            labels["id"] = str(account.id)
            for key in account.__dict__["_fields"].keys():
                if key not in [metric["name"] for metric in METRICS] + IGNORE_KEYS:
                    value = getattr(account, key)
                    if value and value != "Not loaded":
                        labels[key] = str(value)

            for metric in METRICS:
                item = {}
                try:
                    item["name"] = f"woob_bank_{metric['name']}"
                    item["labels"] = labels
                    item["description"] = metric["description"]
                    value = getattr(account, metric["name"])
                    if value and value != "Not loaded":
                        if metric["type"] == "datetime":
                            item["value"] = datetime.strptime(
                                str(value), "%Y-%m-%d"
                            ).timestamp()
                            item["type"] = "counter"
                        else:
                            item["value"] = float(value)
                            item["type"] = metric["type"]
                        metrics.append(item)
                except AttributeError:
                    continue
                except ValueError:
                    continue
                except TypeError:
                    continue

        logging.info("Metrics : %s", metrics)
        return metrics

    def collect(self):
        """Collect Prometheus Metrics"""
        metrics = self.get_metrics()
        for metric in metrics:
            labels = {
                "job": WOOB_BANK_EXPORTER_NAME,
                "name": WOOB_BANK_NAME,
                "module": WOOB_BANK_MODULE,
            }
            labels |= metric["labels"]
            prometheus_metric = Metric(
                metric["name"], metric["description"], metric["type"]
            )
            prometheus_metric.add_sample(
                metric["name"], value=metric["value"], labels=labels
            )
            yield prometheus_metric


def main():
    """Main Function"""
    logging.info("Starting Woob Bank Exporter on port %s.", WOOB_BANK_EXPORTER_PORT)
    logging.debug("WOOB_BANK_EXPORTER_PORT: %s.", WOOB_BANK_EXPORTER_PORT)
    logging.debug("WOOB_BANK_EXPORTER_NAME: %s.", WOOB_BANK_EXPORTER_NAME)
    logging.debug("WOOB_BANK_NAME: %s.", WOOB_BANK_NAME)
    logging.debug("WOOB_BANK_MODULE: %s.", WOOB_BANK_MODULE)
    WoobBankCollector()
    # Start Prometheus HTTP Server
    start_http_server(WOOB_BANK_EXPORTER_PORT)
    # Init WoobBankCollector
    REGISTRY.register(WoobBankCollector())
    # Infinite Loop
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
