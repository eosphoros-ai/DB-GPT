# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/22 下午2:20
'''
from OpenSSL import crypto, SSL


def generate_certificate(
        organization="PrivacyFilter",
        common_name="172.23.52.25:50000",
        country="NL",
        duration=(365 * 24 * 60 * 60),
        keyfilename="key.pem",
        certfilename="cert.pem"):
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)

    cert = crypto.X509()
    cert.get_subject().C = country
    cert.get_subject().O = organization
    cert.get_subject().CN = common_name
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(duration)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha512')

    with open(keyfilename, "wt") as keyfile:
        keyfile.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))
    with open(certfilename, "wt") as certfile:
        certfile.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))


if __name__ == '__main__':
    generate_certificate()
