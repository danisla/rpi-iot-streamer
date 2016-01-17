import os
import re
import docker
from tornado.options import define, options

import logging
logger = logging.getLogger(__file__)

define("docker_host", default=os.environ.get("DOCKER_HOST", None), type=str, help="If specified, connect to this docker host, default is socket")
define("docker_tls_ca", default=os.environ.get("DOCKER_TLS_CA", os.environ.get("DOCKER_CERT_PATH","")+"/ca.pem"), type=str, help="TLS CA cert for docker host")
define("docker_tls_cert", default=os.environ.get("DOCKER_TLS_CERT", os.environ.get("DOCKER_CERT_PATH","")+"/cert.pem"), type=str, help="TLS cert for docker host")
define("docker_tls_key", default=os.environ.get("DOCKER_TLS_KEY", os.environ.get("DOCKER_CERT_PATH","")+"/key.pem"), type=str, help="TLS key for docker host")

def get_docker_client():

    docker_host = options.docker_host
    docker_tls_ca = options.docker_tls_ca
    docker_tls_cert = options.docker_tls_cert
    docker_tls_key = options.docker_tls_key

    if docker_host:

        tls_config = None

        if docker_tls_ca:

            if not os.path.exists(docker_tls_ca):
                raise Exception("Cannot read docker ca file: %s" % docker_tls_ca)

            if not os.path.exists(docker_tls_cert):
                raise Exception("Cannot read docker cert file: %s" % docker_tls_cert)

            if not os.path.exists(docker_tls_key):
                raise Exception("Cannot read docker key file: %s" % docker_tls_key)

            tls_config = docker.tls.TLSConfig(
                ca_cert=docker_tls_ca,
                client_cert=(docker_tls_cert, docker_tls_key),
                verify=True
            )

            if docker_host.startswith("tcp://"):
                docker_host = docker_host.replace("tcp://","https://")
            elif not docker_host.startswith("https://"):
                docker_host = "https://" + docker_host

            logger.debug("Docker host: " + docker_host)

            cli = docker.Client(base_url=docker_host, tls=tls_config, version='auto')

        else:
            logger.warning("Connecting to {0} without TLS certs.")

    else:
        cli = docker.Client()

    return cli


def find_containers(pat_s, all=False):
    pat = re.compile(pat_s)
    cli = get_docker_client()
    containers = []

    for c in cli.containers(all=all):
        for n in c["Names"]:
            if pat.match(n):
                containers.append(c)
    return containers
